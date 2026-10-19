"""Live and cached market data service utilizing yfinance with database fallbacks."""

import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
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

        return LiveQuote(
            symbol=symbol.upper(),
            ticker=f"{symbol.upper()}.NS",
            company_name=sec.company_name if sec else symbol.upper(),
            sector=sec.sector if sec else None,
            industry=sec.industry if sec else None,
            latest_price=price,
            previous_close=prev_close,
            change=round(change, 2) if change is not None else None,
            change_percent=round(change_pct, 2) if change_pct is not None else None,
            day_open=None,
            day_high=None,
            day_low=None,
            volume=None,
            currency="INR",
            as_of=trade_date,
            quote_type="persisted_close",
            is_market_open=False,
            source="database",
            data_quality="fallback",
            error=None,
        )
    except Exception as exc:
        logger.warning("Database fallback failed for symbol %s: %s", symbol, exc)
        return None


def fetch_quote(
    symbol: str,
    session: Session | None = None,
    force_refresh: bool = False,
) -> LiveQuote:
    """Fetch quote for a single symbol using yfinance, with caching and database fallback."""
    raw_symbol, yf_symbol = normalize_symbol_for_yahoo(symbol)

    if not force_refresh:
        cached = _cache.get_quote(raw_symbol)
        if cached:
            return cached

    # Try fetching via yfinance
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

            # Get sector / company details from database if available, or ticker info
            company_name: str | None = None
            sector: str | None = None
            industry: str | None = None

            if session:
                try:
                    alias = session.scalar(
                        select(SecurityAlias).where(
                            SecurityAlias.symbol == raw_symbol,
                            SecurityAlias.exchange == "NSE",
                        )
                    )
                    if alias:
                        sec = session.get(Security, alias.security_id)
                        if sec:
                            company_name = sec.company_name
                            sector = sec.sector
                            industry = sec.industry
                except Exception:
                    pass

            # Fallback to ticker.info for company name or sector if not in DB
            if not company_name or not sector:
                try:
                    t_info = ticker.info
                    company_name = company_name or t_info.get("longName") or t_info.get("shortName") or raw_symbol
                    sector = sector or t_info.get("sector")
                    industry = industry or t_info.get("industry")
                except Exception:
                    company_name = company_name or raw_symbol

            now_iso = datetime.now(UTC).isoformat()
            quote = LiveQuote(
                symbol=raw_symbol,
                ticker=yf_symbol,
                company_name=company_name or raw_symbol,
                sector=sector,
                industry=industry,
                latest_price=round(last_price, 2),
                previous_close=round(prev_close, 2) if prev_close else None,
                change=round(change, 2) if change is not None else None,
                change_percent=round(change_pct, 2) if change_pct is not None else None,
                day_open=round(float(getattr(fast, "open", 0)), 2) if getattr(fast, "open", None) else None,
                day_high=round(float(getattr(fast, "day_high", 0)), 2) if getattr(fast, "day_high", None) else None,
                day_low=round(float(getattr(fast, "day_low", 0)), 2) if getattr(fast, "day_low", None) else None,
                volume=int(getattr(fast, "last_volume", 0)) if getattr(fast, "last_volume", None) else None,
                currency=currency,
                as_of=now_iso,
                quote_type="live_quote",
                is_market_open=None,
                source="yfinance",
                data_quality="live",
                error=None,
            )
            _cache.set_quote(raw_symbol, quote)
            return quote
    except Exception as exc:
        logger.info("yfinance quote lookup failed for %s: %s", yf_symbol, exc)

    # If yfinance failed or returned no price, attempt database fallback
    if session:
        fallback = _fallback_from_database(raw_symbol, session)
        if fallback:
            _cache.set_quote(raw_symbol, fallback)
            return fallback

    # If everything fails, report graceful error without fabricating price
    error_quote = LiveQuote(
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
        error=f"Price unavailable for {raw_symbol}. Verified ticker or network connection required.",
    )
    return error_quote


def fetch_benchmark(force_refresh: bool = False) -> BenchmarkQuote:
    """Fetch benchmark quote (^NSEI / NIFTY 50) with caching."""
    if not force_refresh:
        cached = _cache.get_benchmark()
        if cached:
            return cached

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
        logger.warning("Failed to fetch benchmark %s: %s", BENCHMARK_SYMBOL, exc)

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
    """Retrieve quotes for multiple symbols and benchmark in a single optimized pass."""
    quotes: dict[str, dict[str, Any]] = {}

    for sym in symbols:
        raw = sym.strip().upper()
        if not raw:
            continue
        q = fetch_quote(raw, session=session, force_refresh=force_refresh)
        quotes[raw] = q.to_dict()

    benchmark = fetch_benchmark(force_refresh=force_refresh)

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
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Retrieve historical OHLCV data bars for a symbol with caching."""
    raw_symbol, yf_symbol = normalize_symbol_for_yahoo(symbol)

    if not force_refresh:
        cached = _cache.get_history(raw_symbol, period)
        if cached:
            return [b.to_dict() for b in cached]

    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)

        if df.empty:
            return []

        bars: list[HistoricalBar] = []
        for index, row in df.iterrows():
            trade_date = pd.Timestamp(index).strftime("%Y-%m-%d")
            close_val = float(row["Close"]) if not pd.isna(row["Close"]) else 0.0
            adj_close_val = float(row.get("Adj Close", close_val)) if not pd.isna(row.get("Adj Close", close_val)) else close_val
            open_val = float(row["Open"]) if not pd.isna(row["Open"]) else close_val
            high_val = float(row["High"]) if not pd.isna(row["High"]) else close_val
            low_val = float(row["Low"]) if not pd.isna(row["Low"]) else close_val
            volume_val = int(row["Volume"]) if not pd.isna(row["Volume"]) else 0

            bars.append(
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

        _cache.set_history(raw_symbol, period, bars)
        return [b.to_dict() for b in bars]
    except Exception as exc:
        logger.error("Failed to fetch historical OHLCV for %s: %s", yf_symbol, exc)
        return []
