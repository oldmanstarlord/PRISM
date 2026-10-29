"""Live and cached market data service utilizing yfinance with database fallbacks."""

import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import yfinance as yf  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import PriceDailyAdjusted, Security, SecurityAlias

logger = logging.getLogger(__name__)

QUOTE_CACHE_TTL_SECONDS = 60
HISTORY_CACHE_TTL_SECONDS = 300
BENCHMARK_CACHE_TTL_SECONDS = 60

BENCHMARK_SYMBOL = "^NSEI"
BENCHMARK_NAME = "NIFTY 50"


@dataclass(slots=True)
class LiveQuote:
    symbol: str
    ticker: str
    company_name: str | None
    sector: str | None
    industry: str | None
    latest_price: float | None
    previous_close: float | None
    change: float | None
    change_percent: float | None
    day_open: float | None
    day_high: float | None
    day_low: float | None
    volume: int | None
    currency: str
    as_of: str
    quote_type: str  # "live_quote" | "latest_close" | "persisted_close" | "unknown"
    is_market_open: bool | None
    source: str  # "yfinance" | "database" | "unavailable"
    data_quality: str  # "live" | "eod" | "cached" | "fallback" | "error"
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BenchmarkQuote:
    symbol: str
    name: str
    latest_price: float | None
    previous_close: float | None
    change: float | None
    change_percent: float | None
    as_of: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HistoricalBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketDataCache:
    """Thread-safe TTL in-memory cache for quotes and historical prices."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._quotes: dict[str, tuple[float, LiveQuote]] = {}
        self._history: dict[tuple[str, str], tuple[float, list[HistoricalBar]]] = {}
        self._benchmark: tuple[float, BenchmarkQuote] | None = None

    def get_quote(self, symbol: str) -> LiveQuote | None:
        with self._lock:
            entry = self._quotes.get(symbol.upper())
            if entry and (time.time() - entry[0]) < QUOTE_CACHE_TTL_SECONDS:
                return entry[1]
            return None

    def set_quote(self, symbol: str, quote: LiveQuote) -> None:
        with self._lock:
            self._quotes[symbol.upper()] = (time.time(), quote)

    def get_benchmark(self) -> BenchmarkQuote | None:
        with self._lock:
            if self._benchmark and (time.time() - self._benchmark[0]) < BENCHMARK_CACHE_TTL_SECONDS:
                return self._benchmark[1]
            return None

    def set_benchmark(self, quote: BenchmarkQuote) -> None:
        with self._lock:
            self._benchmark = (time.time(), quote)

    def get_history(self, symbol: str, period: str) -> list[HistoricalBar] | None:
        with self._lock:
            entry = self._history.get((symbol.upper(), period))
            if entry and (time.time() - entry[0]) < HISTORY_CACHE_TTL_SECONDS:
                return entry[1]
            return None

    def set_history(self, symbol: str, period: str, bars: list[HistoricalBar]) -> None:
        with self._lock:
            self._history[(symbol.upper(), period)] = (time.time(), bars)

    def clear(self) -> None:
        with self._lock:
            self._quotes.clear()
            self._history.clear()
            self._benchmark = None


_cache = MarketDataCache()


def normalize_symbol_for_yahoo(symbol: str) -> tuple[str, str]:
    """Return normalized raw symbol and yfinance ticker (appending .NS for Indian stocks)."""
    clean = symbol.strip().upper()
    if clean.startswith("^"):
        return clean, clean
    if clean.endswith(".NS") or clean.endswith(".BO"):
        raw = clean.split(".")[0]
        return raw, clean
    return clean, f"{clean}.NS"


def _fallback_from_database(symbol: str, session: Session) -> LiveQuote | None:
    """Retrieve the latest known closing price and security metadata from the local database."""
    try:
        alias = session.scalar(
            select(SecurityAlias).where(
                SecurityAlias.symbol == symbol.upper(),
                SecurityAlias.exchange == "NSE",
            )
        )
        if alias is None:
            return None

        sec = session.get(Security, alias.security_id)
        latest_price_row = session.execute(
            select(PriceDailyAdjusted.adjusted_close, PriceDailyAdjusted.trade_date)
            .where(PriceDailyAdjusted.security_id == alias.security_id)
            .order_by(PriceDailyAdjusted.trade_date.desc())
            .limit(1)
        ).first()

        if latest_price_row is None:
            return None

        price = float(latest_price_row.adjusted_close)
        trade_date = latest_price_row.trade_date.isoformat()

        # Check for previous day's close for day change calculation
        prev_price_row = session.execute(
            select(PriceDailyAdjusted.adjusted_close)
            .where(
                PriceDailyAdjusted.security_id == alias.security_id,
                PriceDailyAdjusted.trade_date < latest_price_row.trade_date,
            )
            .order_by(PriceDailyAdjusted.trade_date.desc())
            .limit(1)
        ).first()
        prev_close = float(prev_price_row.adjusted_close) if prev_price_row else None
        change = (price - prev_close) if prev_close else None
        change_pct = ((price - prev_close) / prev_close * 100.0) if prev_close else None

        # Fetch corresponding raw OHLCV for intraday reference and volume
        from backend.app.db.models import PriceDailyRaw

        raw_price_row = session.execute(
            select(
                PriceDailyRaw.open,
                PriceDailyRaw.high,
                PriceDailyRaw.low,
                PriceDailyRaw.close,
                PriceDailyRaw.volume,
                PriceDailyRaw.quality_flags,
            )
            .where(
                PriceDailyRaw.security_id == alias.security_id,
                PriceDailyRaw.trade_date == latest_price_row.trade_date,
            )
            .order_by(PriceDailyRaw.source_revision.desc())
            .limit(1)
        ).first()

        day_open = float(raw_price_row.open) if raw_price_row else None
        day_high = float(raw_price_row.high) if raw_price_row else None
        day_low = float(raw_price_row.low) if raw_price_row else None
        volume = int(raw_price_row.volume) if raw_price_row else None

        # Determine freshness status: if trade date is within 5 calendar days, verified; else stale
        days_stale = (datetime.now(UTC).date() - latest_price_row.trade_date).days
        data_quality = "stale" if days_stale > 7 else "verified"

        return LiveQuote(
            symbol=symbol.upper(),
            ticker=f"{symbol.upper()}.NS",
            company_name=sec.company_name if sec else symbol.upper(),
            sector=sec.sector if sec else None,
            industry=sec.industry if sec else None,
            latest_price=round(price, 2),
            previous_close=round(prev_close, 2) if prev_close else None,
            change=round(change, 2) if change is not None else None,
            change_percent=round(change_pct, 2) if change_pct is not None else None,
            day_open=round(day_open, 2) if day_open is not None else None,
            day_high=round(day_high, 2) if day_high is not None else None,
            day_low=round(day_low, 2) if day_low is not None else None,
            volume=volume,
            currency="INR",
            as_of=trade_date,
            quote_type="persisted_close",
            is_market_open=False,
            source="database",
            data_quality=data_quality,
            error=None,
        )
    except Exception as exc:
        logger.warning("Database quote query failed for symbol %s: %s", symbol, type(exc).__name__)
        return None


def _fetch_from_yfinance(raw_symbol: str, yf_symbol: str) -> LiveQuote | None:
    """Fetch live quote from yfinance."""
    try:
        ticker = yf.Ticker(yf_symbol)
        fast = ticker.fast_info

        last_price = getattr(fast, "last_price", None)
        prev_close = getattr(fast, "previous_close", None)
        currency = getattr(fast, "currency", "INR") or "INR"

        if last_price is not None and not pd.isna(last_price):
            last_price = float(last_price)
            prev_close = float(prev_close) if prev_close and not pd.isna(prev_close) else None

            change = (last_price - prev_close) if prev_close else None
            change_pct = ((last_price - prev_close) / prev_close * 100.0) if prev_close else None

            company_name: str | None = None
            sector: str | None = None
            industry: str | None = None

            try:
                t_info = ticker.info
                name_cand = t_info.get("longName") or t_info.get("shortName")
                company_name = name_cand or raw_symbol
                sector = t_info.get("sector")
                industry = t_info.get("industry")
            except Exception:
                company_name = raw_symbol

            now_iso = datetime.now(UTC).isoformat()
            fast_open = getattr(fast, "open", None)
            fast_high = getattr(fast, "day_high", None)
            fast_low = getattr(fast, "day_low", None)
            fast_vol = getattr(fast, "last_volume", None)
            return LiveQuote(
                symbol=raw_symbol,
                ticker=yf_symbol,
                company_name=company_name or raw_symbol,
                sector=sector,
                industry=industry,
                latest_price=round(last_price, 2),
                previous_close=round(prev_close, 2) if prev_close else None,
                change=round(change, 2) if change is not None else None,
                change_percent=round(change_pct, 2) if change_pct is not None else None,
                day_open=round(float(fast_open), 2) if fast_open else None,
                day_high=round(float(fast_high), 2) if fast_high else None,
                day_low=round(float(fast_low), 2) if fast_low else None,
                volume=int(fast_vol) if fast_vol else None,
                currency=currency,
                as_of=now_iso,
                quote_type="live_quote",
                is_market_open=None,
                source="yfinance",
                data_quality="live",
                error=None,
            )
    except Exception as exc:
        logger.info("yfinance quote lookup failed for %s: %s", yf_symbol, exc)
    return None


def fetch_quote(
    symbol: str,
    session: Session | None = None,
    force_refresh: bool = False,
) -> LiveQuote:
    """Fetch quote for a single symbol.

    Prioritizes fresh live quotes from yfinance when force_refresh=True,
    with clean database persistence fallback.
    """
    raw_symbol, yf_symbol = normalize_symbol_for_yahoo(symbol)

    if not force_refresh:
        cached = _cache.get_quote(raw_symbol)
        if cached:
            return cached

    # When force_refresh is requested, attempt live yfinance quote first
    if force_refresh:
        live_q = _fetch_from_yfinance(raw_symbol, yf_symbol)
        if live_q is not None and live_q.latest_price is not None:
            _cache.set_quote(raw_symbol, live_q)
            return live_q

    # Persisted database query
    if session is not None:
        db_quote = _fallback_from_database(raw_symbol, session)
        if db_quote is not None:
            _cache.set_quote(raw_symbol, db_quote)
            return db_quote

    # Live lookup if not found in database or session is None
    live_q = _fetch_from_yfinance(raw_symbol, yf_symbol)
    if live_q is not None:
        _cache.set_quote(raw_symbol, live_q)
        return live_q

    return LiveQuote(
        symbol=raw_symbol,
        ticker=yf_symbol,
        company_name=raw_symbol,
        sector=None,
        industry=None,
        latest_price=None,
        previous_close=None,
        change=None,
        change_percent=None,
        day_open=None,
        day_high=None,
        day_low=None,
        volume=None,
        currency="INR",
        as_of=datetime.now(UTC).isoformat(),
        quote_type="unknown",
        is_market_open=None,
        source="unavailable",
        data_quality="error",
        error=(
            f"Price unavailable for {raw_symbol}. Price series not found in database. "
            "Verified ingestion via pipeline required."
        ),
    )


def fetch_benchmark(
    session: Session | None = None,
    force_refresh: bool = False,
) -> BenchmarkQuote:
    """Fetch benchmark quote (^NSEI / NIFTY 50), preferring database persistence."""
    if not force_refresh:
        cached = _cache.get_benchmark()
        if cached:
            return cached

    # Prefer database persistence if session is provided
    if session is not None:
        try:
            alias = session.scalar(
                select(SecurityAlias).where(
                    SecurityAlias.symbol == BENCHMARK_SYMBOL,
                    SecurityAlias.exchange == "NSE",
                )
            )
            if alias:
                latest_row = session.execute(
                    select(PriceDailyAdjusted.adjusted_close, PriceDailyAdjusted.trade_date)
                    .where(PriceDailyAdjusted.security_id == alias.security_id)
                    .order_by(PriceDailyAdjusted.trade_date.desc())
                    .limit(1)
                ).first()
                if latest_row:
                    price = float(latest_row.adjusted_close)
                    prev_row = session.execute(
                        select(PriceDailyAdjusted.adjusted_close)
                        .where(
                            PriceDailyAdjusted.security_id == alias.security_id,
                            PriceDailyAdjusted.trade_date < latest_row.trade_date,
                        )
                        .order_by(PriceDailyAdjusted.trade_date.desc())
                        .limit(1)
                    ).first()
                    prev_c = float(prev_row.adjusted_close) if prev_row else None
                    chg = (price - prev_c) if prev_c else None
                    chg_pct = ((price - prev_c) / prev_c * 100.0) if prev_c else None

                    bm_quote = BenchmarkQuote(
                        symbol=BENCHMARK_SYMBOL,
                        name=BENCHMARK_NAME,
                        latest_price=round(price, 2),
                        previous_close=round(prev_c, 2) if prev_c else None,
                        change=round(chg, 2) if chg is not None else None,
                        change_percent=round(chg_pct, 2) if chg_pct is not None else None,
                        as_of=latest_row.trade_date.isoformat(),
                    )
                    _cache.set_benchmark(bm_quote)
                    return bm_quote
        except Exception as exc:
            logger.warning("Database benchmark query failed: %s", type(exc).__name__)

    # Outside request path or fallback
    try:
        ticker = yf.Ticker(BENCHMARK_SYMBOL)
        fast = ticker.fast_info
        last_price = getattr(fast, "last_price", None)
        prev_close = getattr(fast, "previous_close", None)

        if last_price and not pd.isna(last_price):
            last_p = float(last_price)
            prev_c = float(prev_close) if prev_close and not pd.isna(prev_close) else None
            change = (last_p - prev_c) if prev_c else None
            change_pct = ((last_p - prev_c) / prev_c * 100.0) if prev_c else None

            quote = BenchmarkQuote(
                symbol=BENCHMARK_SYMBOL,
                name=BENCHMARK_NAME,
                latest_price=round(last_p, 2),
                previous_close=round(prev_c, 2) if prev_c else None,
                change=round(change, 2) if change is not None else None,
                change_percent=round(change_pct, 2) if change_pct is not None else None,
                as_of=datetime.now(UTC).isoformat(),
            )
            _cache.set_benchmark(quote)
            return quote
    except Exception as exc:
        logger.warning("Failed to fetch benchmark %s: %s", BENCHMARK_SYMBOL, type(exc).__name__)

    return BenchmarkQuote(
        symbol=BENCHMARK_SYMBOL,
        name=BENCHMARK_NAME,
        latest_price=None,
        previous_close=None,
        change=None,
        change_percent=None,
        as_of=datetime.now(UTC).isoformat(),
    )


def fetch_batch_quotes(
    symbols: list[str],
    session: Session | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Retrieve quotes for multiple symbols and benchmark in a single pass."""
    quotes: dict[str, dict[str, Any]] = {}

    for sym in symbols:
        raw = sym.strip().upper()
        if not raw:
            continue
        q = fetch_quote(raw, session=session, force_refresh=force_refresh)
        quotes[raw] = q.to_dict()

    benchmark = fetch_benchmark(session=session, force_refresh=force_refresh)

    return {
        "quotes": quotes,
        "benchmark": benchmark.to_dict(),
        "timestamp": datetime.now(UTC).isoformat(),
        "count": len(quotes),
    }


def fetch_historical_ohlcv(
    symbol: str,
    period: str = "1mo",
    interval: str = "1d",
    session: Session | None = None,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Retrieve historical daily OHLCV bars for a symbol from database or cache."""
    raw_symbol, yf_symbol = normalize_symbol_for_yahoo(symbol)

    if not force_refresh:
        cached = _cache.get_history(raw_symbol, period)
        if cached:
            return [b.to_dict() for b in cached]

    # Map period to days
    period_days_map = {
        "5d": 7,
        "1mo": 35,
        "3mo": 105,
        "6mo": 200,
        "1y": 380,
        "2y": 750,
        "5y": 1900,
        "max": 5000,
    }
    days = period_days_map.get(period, 35)

    if session is not None:
        try:
            from backend.app.db.models import PriceDailyRaw

            alias = session.scalar(
                select(SecurityAlias).where(
                    SecurityAlias.symbol == raw_symbol,
                    SecurityAlias.exchange == "NSE",
                )
            )
            if alias:
                cutoff_date = datetime.now(UTC).date() - timedelta(days=days)
                rows = session.execute(
                    select(
                        PriceDailyRaw.trade_date,
                        PriceDailyRaw.open,
                        PriceDailyRaw.high,
                        PriceDailyRaw.low,
                        PriceDailyRaw.close,
                        PriceDailyRaw.volume,
                        PriceDailyAdjusted.adjusted_close,
                    )
                    .join(
                        PriceDailyAdjusted,
                        (PriceDailyAdjusted.security_id == PriceDailyRaw.security_id)
                        & (PriceDailyAdjusted.trade_date == PriceDailyRaw.trade_date),
                    )
                    .where(
                        PriceDailyRaw.security_id == alias.security_id,
                        PriceDailyRaw.trade_date >= cutoff_date,
                    )
                    .order_by(PriceDailyRaw.trade_date.asc())
                ).all()

                if rows:
                    bars = [
                        HistoricalBar(
                            date=r.trade_date.isoformat(),
                            open=round(float(r.open), 2),
                            high=round(float(r.high), 2),
                            low=round(float(r.low), 2),
                            close=round(float(r.close), 2),
                            adjusted_close=round(float(r.adjusted_close), 2),
                            volume=int(r.volume),
                        )
                        for r in rows
                    ]
                    _cache.set_history(raw_symbol, period, bars)
                    return [b.to_dict() for b in bars]
        except Exception as exc:
            logger.warning("Database OHLCV query failed for %s: %s", raw_symbol, type(exc).__name__)

    # Outside request path without DB session (e.g. tests)
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)

        if df.empty:
            return []

        bars_list: list[HistoricalBar] = []
        for index, row in df.iterrows():
            trade_date = pd.Timestamp(index).strftime("%Y-%m-%d")
            close_val = float(row["Close"]) if not pd.isna(row["Close"]) else 0.0
            raw_adj = row.get("Adj Close", close_val)
            adj_close_val = float(raw_adj) if not pd.isna(raw_adj) else close_val
            open_val = float(row["Open"]) if not pd.isna(row["Open"]) else close_val
            high_val = float(row["High"]) if not pd.isna(row["High"]) else close_val
            low_val = float(row["Low"]) if not pd.isna(row["Low"]) else close_val
            volume_val = int(row["Volume"]) if not pd.isna(row["Volume"]) else 0

            bars_list.append(
                HistoricalBar(
                    date=trade_date,
                    open=round(open_val, 2),
                    high=round(high_val, 2),
                    low=round(low_val, 2),
                    close=round(close_val, 2),
                    adjusted_close=round(adj_close_val, 2),
                    volume=volume_val,
                )
            )

        _cache.set_history(raw_symbol, period, bars_list)
        return [b.to_dict() for b in bars_list]
    except Exception as exc:
        logger.error("Failed to fetch historical OHLCV for %s: %s", yf_symbol, type(exc).__name__)
        return []


def get_market_data_health(session: Session) -> dict[str, Any]:
    """Report provider health, database coverage, benchmark status, and limitations."""
    from sqlalchemy import func

    from backend.app.db.models import PipelineRun, PriceDailyAdjusted, Security

    last_run = session.scalar(
        select(PipelineRun)
        .where(PipelineRun.workflow == "daily_market_data", PipelineRun.status == "completed")
        .order_by(PipelineRun.completed_at.desc())
        .limit(1)
    )

    sec_count = session.scalar(select(func.count(Security.id))) or 0
    price_count = session.scalar(select(func.count(PriceDailyAdjusted.id))) or 0
    latest_trade_date = session.scalar(select(func.max(PriceDailyAdjusted.trade_date)))

    # Benchmark status
    bm_alias = session.scalar(
        select(SecurityAlias).where(
            SecurityAlias.symbol == BENCHMARK_SYMBOL,
            SecurityAlias.exchange == "NSE",
        )
    )
    bm_date = None
    if bm_alias:
        bm_date = session.scalar(
            select(func.max(PriceDailyAdjusted.trade_date)).where(
                PriceDailyAdjusted.security_id == bm_alias.security_id
            )
        )

    return {
        "provider": "yfinance (batch pipeline)",
        "status": "operational",
        "last_successful_ingestion": (
            last_run.completed_at.isoformat() if last_run and last_run.completed_at else None
        ),
        "latest_market_date": latest_trade_date.isoformat() if latest_trade_date else None,
        "stored_securities_count": sec_count,
        "stored_price_records": price_count,
        "benchmark_symbol": BENCHMARK_SYMBOL,
        "benchmark_status": "synced" if bm_date else "pending_ingestion",
        "benchmark_latest_date": bm_date.isoformat() if bm_date else None,
        "survivorship_limitation": (
            "Historical universe is restricted to active NIFTY 200 constituents as of 2026-09-30; "
            "historical index additions/deletions prior to that date are not reconstructed."
        ),
    }


def align_price_series(
    asset_series: pd.Series,
    benchmark_series: pd.Series,
    asset_name: str = "asset",
    benchmark_name: str = "benchmark",
    min_observations: int = 20,
) -> tuple[pd.Series, pd.Series, dict[str, Any]]:
    """Align asset and benchmark series on common valid trading dates.

    Ensures zero silent mixing of data conventions and provides observation count
    and coverage metadata.
    """
    df = pd.concat([asset_series, benchmark_series], axis=1, join="inner").dropna()
    df.columns = [asset_name, benchmark_name]

    obs = len(df)
    asset_orig = len(asset_series.dropna())
    bench_orig = len(benchmark_series.dropna())
    coverage = float(obs / max(bench_orig, 1))

    is_sufficient = obs >= min_observations
    warning = None
    if not is_sufficient:
        warning = (
            f"Insufficient common observations ({obs} < {min_observations}) "
            f"between {asset_name} and {benchmark_name}."
        )

    meta = {
        "observation_count": obs,
        "asset_original_count": asset_orig,
        "benchmark_original_count": bench_orig,
        "coverage_ratio": coverage,
        "is_sufficient": is_sufficient,
        "warning": warning,
    }
    return df[asset_name], df[benchmark_name], meta
