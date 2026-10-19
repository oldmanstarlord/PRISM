"""Stock-level explainable risk assessment and portfolio diversification."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import yfinance as yf  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import PriceDailyAdjusted, SecurityAlias
from backend.app.market_data.live_service import normalize_symbol_for_yahoo
from backend.app.sector_divergence.service import latest_completed_run_query

ANNUALISATION_FACTOR = 252
BENCHMARK_SYMBOL = "^NSEI"

RiskLevel = Literal["Low", "Moderate", "High", "Very High"]
DiversificationGrade = Literal["A", "B", "C", "D"]


@dataclass(slots=True)
class WindowRiskMetrics:
    window: str  # "1M" | "3M" | "6M" | "1Y"
    observations: int
    annualized_volatility: float
    downside_volatility: float
    max_drawdown: float
    beta: float
    alpha: float
    price_instability: float
    stock_return: float
    benchmark_return: float
    excess_return: float


@dataclass(slots=True)
class RiskFactorBreakdown:
    factor_name: str
    raw_value: float
    normalized_score: float  # 0 to 100
    weight: float
    contribution: float
    interpretation: str


@dataclass(slots=True)
class StockRiskProfile:
    symbol: str
    company_name: str
    sector: str
    weight: float
    overall_score: float  # 0 to 100
    risk_classification: RiskLevel
    color: str
    primary_drivers: list[str]
    narrative_explanation: str
    factors: list[RiskFactorBreakdown]
    windows: dict[str, WindowRiskMetrics]  # "1M", "3M", "6M", "1Y"
    # Performance since purchase date (if purchase info provided)
    purchase_price: float | None
    current_price: float | None
    unrealized_pnl: float | None
    unrealized_return: float | None
    drawdown_since_purchase: float | None
    volatility_since_purchase: float | None
    recent_risk_change: str  # "increasing" | "stable" | "decreasing"
    sector_divergence_20d: float | None
    sector_divergence_band: str | None
    sector_relative_performance: float | None
    benchmark_relative_performance: float | None
    data_coverage: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PortfolioRiskProfile:
    portfolio_risk_score: float
    portfolio_classification: RiskLevel
    portfolio_color: str
    annualized_volatility: float
    downside_volatility: float
    max_drawdown: float
    portfolio_beta: float
    holding_hhi: float
    effective_holdings: float
    sector_hhi: float
    effective_sectors: float
    diversification_ratio: float
    diversification_score: float
    diversification_grade: DiversificationGrade
    diversification_interpretation: str
    risk_contributions: list[dict[str, Any]]
    sector_exposure: list[dict[str, Any]]
    correlation_matrix: dict[str, dict[str, float]]
    historical_risk_trend: str
    summary_findings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── In-memory cache for benchmark returns ───
_benchmark_returns_cache: tuple[float, pd.Series] | None = None


def get_benchmark_returns() -> pd.Series:
    """Fetch and cache daily log returns for NIFTY 50 (^NSEI)."""
    global _benchmark_returns_cache
    now = datetime.now().timestamp()
    if _benchmark_returns_cache and (now - _benchmark_returns_cache[0]) < 3600:
        return _benchmark_returns_cache[1]

    try:
        ticker = yf.Ticker(BENCHMARK_SYMBOL)
        df = ticker.history(period="2y", interval="1d", auto_adjust=False)
        if not df.empty and "Close" in df.columns:
            closes = df["Close"].dropna()
            returns = np.log(closes / closes.shift(1)).dropna()
            returns.index = pd.to_datetime(returns.index).tz_localize(None).date
            _benchmark_returns_cache = (now, returns)
            return returns
    except Exception:
        pass

    # Fallback to an empty series
    return pd.Series(dtype=float)


def _load_stock_prices_from_db(
    session: Session,
    symbols: list[str],
    days: int = 500,
) -> pd.DataFrame:
    """Load daily adjusted closing prices for given symbols from PriceDailyAdjusted."""
    aliases = session.execute(
        select(SecurityAlias.symbol, SecurityAlias.security_id).where(
            SecurityAlias.symbol.in_([s.upper() for s in symbols]),
            SecurityAlias.exchange == "NSE",
        )
    ).all()

    if not aliases:
        return pd.DataFrame()

    sec_map = {row.symbol: row.security_id for row in aliases}
    sec_ids = list(sec_map.values())

    from sqlalchemy import func

    subq = (
        select(
            PriceDailyAdjusted.trade_date,
            PriceDailyAdjusted.security_id,
            PriceDailyAdjusted.adjusted_close,
            func.row_number()
            .over(
                partition_by=(
                    PriceDailyAdjusted.security_id,
                    PriceDailyAdjusted.trade_date,
                ),
                order_by=(
                    PriceDailyAdjusted.computed_at.desc(),
                    PriceDailyAdjusted.id.desc(),
                ),
            )
            .label("rn"),
        )
        .where(PriceDailyAdjusted.security_id.in_(sec_ids))
        .subquery()
    )
    prices_q = (
        select(subq.c.trade_date, subq.c.security_id, subq.c.adjusted_close)
        .where(subq.c.rn == 1)
        .order_by(subq.c.trade_date.desc())
    )
    rows = session.execute(prices_q).all()
    if not rows:
        return pd.DataFrame()

    sec_to_sym = {v: k for k, v in sec_map.items()}
    records = [
        {
            "date": r.trade_date,
            "symbol": sec_to_sym[r.security_id],
            "price": float(r.adjusted_close),
        }
        for r in rows
        if r.security_id in sec_to_sym
    ]
    df = pd.DataFrame(records)
    df = df.drop_duplicates(subset=["date", "symbol"], keep="first")
    pivot = df.pivot(index="date", columns="symbol", values="price").sort_index()
    return pivot.tail(days)


def _load_stock_prices_yfinance(symbols: list[str], period: str = "2y") -> pd.DataFrame:
    """Fetch historical daily adjusted closes via yfinance as secondary source."""
    frames: dict[str, pd.Series] = {}
    for sym in symbols:
        raw_sym, yf_sym = normalize_symbol_for_yahoo(sym)
        try:
            ticker = yf.Ticker(yf_sym)
            df = ticker.history(period=period, interval="1d", auto_adjust=False)
            if not df.empty and "Adj Close" in df.columns:
                series = df["Adj Close"].dropna()
                series.index = pd.to_datetime(series.index).tz_localize(None).date
                frames[raw_sym] = series
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    return pd.DataFrame(frames).sort_index()


def _normalize_factor(
    value: float,
    low_bound: float,
    high_bound: float,
    invert: bool = False,
) -> float:
    """Linearly normalize raw factor into a clean 0 to 100 scale."""
    if high_bound <= low_bound:
        return 50.0
    scaled = (value - low_bound) / (high_bound - low_bound) * 100.0
    clipped = float(np.clip(scaled, 0.0, 100.0))
    res = 100.0 - clipped if invert else clipped
    return round(float(res), 4)


def _classify_risk(score: float) -> tuple[RiskLevel, str]:
    if score < 30:
        return "Low", "#2e7d32"
    if score < 55:
        return "Moderate", "#ed6c02"
    if score < 80:
        return "High", "#e65100"
    return "Very High", "#d32f2f"


def calculate_single_window_metrics(
    stock_returns: pd.Series,
    benchmark_returns: pd.Series,
    window_days: int,
    window_label: str,
) -> WindowRiskMetrics:
    """Calculate exact volatility, downside volatility, drawdown, alpha and beta."""
    aligned = pd.concat([stock_returns, benchmark_returns], axis=1, join="inner").dropna()
    aligned.columns = ["stock", "benchmark"]
    aligned = aligned.tail(window_days)

    obs = len(aligned)
    if obs < 10:
        return WindowRiskMetrics(
            window=window_label,
            observations=obs,
            annualized_volatility=0.0,
            downside_volatility=0.0,
            max_drawdown=0.0,
            beta=1.0,
            alpha=0.0,
            price_instability=1.0,
            stock_return=0.0,
            benchmark_return=0.0,
            excess_return=0.0,
        )

    r_stock = aligned["stock"].to_numpy()
    r_bench = aligned["benchmark"].to_numpy()

    # Annualized Volatility
    ann_vol = float(np.std(r_stock, ddof=1) * math.sqrt(ANNUALISATION_FACTOR))

    # Downside Volatility (semi-deviation below zero)
    neg_returns = np.minimum(r_stock, 0.0)
    downside_vol = float(
        math.sqrt(np.mean(np.square(neg_returns))) * math.sqrt(ANNUALISATION_FACTOR)
    )

    # Wealth and Drawdown
    wealth = np.exp(np.cumsum(r_stock))
    running_peak = np.maximum.accumulate(wealth)
    drawdowns = wealth / running_peak - 1.0
    max_dd = float(abs(np.min(drawdowns)))

    # Beta and Alpha (vs NIFTY 50)
    bench_var = float(np.var(r_bench, ddof=1))
    if bench_var > 1e-12:
        cov = float(np.cov(r_stock, r_bench, ddof=1)[0, 1])
        beta = float(cov / bench_var)
    else:
        beta = 1.0

    stock_mean = float(np.mean(r_stock))
    bench_mean = float(np.mean(r_bench))
    alpha = float((stock_mean - beta * bench_mean) * ANNUALISATION_FACTOR)

    # Price Instability: ratio of short-term (10-day) vol to window vol
    if obs >= 20:
        recent_10d_vol = float(np.std(r_stock[-10:], ddof=1) * math.sqrt(ANNUALISATION_FACTOR))
        price_instability = float(recent_10d_vol / max(ann_vol, 0.05))
    else:
        price_instability = 1.0

    total_stock_ret = float(np.exp(np.sum(r_stock)) - 1.0)
    total_bench_ret = float(np.exp(np.sum(r_bench)) - 1.0)
    excess_ret = float(total_stock_ret - total_bench_ret)

    return WindowRiskMetrics(
        window=window_label,
        observations=obs,
        annualized_volatility=round(ann_vol, 4),
        downside_volatility=round(downside_vol, 4),
        max_drawdown=round(max_dd, 4),
        beta=round(beta, 3),
        alpha=round(alpha, 4),
        price_instability=round(price_instability, 2),
        stock_return=round(total_stock_ret, 4),
        benchmark_return=round(total_bench_ret, 4),
        excess_return=round(excess_ret, 4),
    )


def calculate_stock_risk(
    symbol: str,
    prices_series: pd.Series,
    benchmark_returns: pd.Series,
    holding_info: dict[str, Any] | None = None,
    sector_divergence_info: tuple[float, str, float | None] | tuple[float, str] | None = None,
) -> StockRiskProfile:
    """Calculate multi-window explainable risk scoring for a single stock."""
    returns = np.log(prices_series / prices_series.shift(1)).dropna()

    # Calculate metrics across 4 standard financial horizons
    windows_map = {
        "1M": 21,
        "3M": 63,
        "6M": 126,
        "1Y": 252,
    }
    windows_metrics = {
        name: calculate_single_window_metrics(returns, benchmark_returns, days, name)
        for name, days in windows_map.items()
    }

    # Primary baseline window is 1Y (or largest available if < 252)
    base_m = (
        windows_metrics["1Y"] if windows_metrics["1Y"].observations >= 60 else windows_metrics["6M"]
    )

    # ─── 5 Normalized Factor Scores (each 0–100) ───
    # Factor 1: Annualized Volatility (weight 30%)
    vol_score = _normalize_factor(base_m.annualized_volatility, 0.12, 0.42)

    # Factor 2: Downside Deviation (weight 25%)
    down_score = _normalize_factor(base_m.downside_volatility, 0.08, 0.30)

    # Factor 3: Maximum Drawdown (weight 20%)
    dd_score = _normalize_factor(base_m.max_drawdown, 0.08, 0.45)

    # Factor 4: Market Beta (weight 15%): Beta=1.0 is ~50; Beta>1.4 is high risk
    beta_score = float(np.clip(50.0 + (base_m.beta - 1.0) * 55.0, 0.0, 100.0))

    # Factor 5: Price Instability & Sector Divergence (weight 10%)
    div_penalty = 0.0
    if sector_divergence_info and abs(sector_divergence_info[0]) > 2.0:
        div_penalty = min(abs(sector_divergence_info[0]) * 8.0, 25.0)
    instability_score = float(
        np.clip(50.0 + (base_m.price_instability - 1.0) * 60.0 + div_penalty, 0.0, 100.0)
    )

    factors = [
        RiskFactorBreakdown(
            factor_name="Annualized Volatility",
            raw_value=round(base_m.annualized_volatility * 100, 2),
            normalized_score=round(vol_score, 1),
            weight=0.30,
            contribution=round(vol_score * 0.30, 2),
            interpretation=f"{base_m.annualized_volatility * 100:.1f}% annual standard deviation",
        ),
        RiskFactorBreakdown(
            factor_name="Downside Volatility",
            raw_value=round(base_m.downside_volatility * 100, 2),
            normalized_score=round(down_score, 1),
            weight=0.25,
            contribution=round(down_score * 0.25, 2),
            interpretation=f"{base_m.downside_volatility * 100:.1f}% semi-deviation on down days",
        ),
        RiskFactorBreakdown(
            factor_name="Maximum Drawdown",
            raw_value=round(base_m.max_drawdown * 100, 2),
            normalized_score=round(dd_score, 1),
            weight=0.20,
            contribution=round(dd_score * 0.20, 2),
            interpretation=(
                f"-{base_m.max_drawdown * 100:.1f}% peak-to-trough decline over {base_m.window}"
            ),
        ),
        RiskFactorBreakdown(
            factor_name="Market Beta (NIFTY 50)",
            raw_value=round(base_m.beta, 2),
            normalized_score=round(beta_score, 1),
            weight=0.15,
            contribution=round(beta_score * 0.15, 2),
            interpretation=f"{base_m.beta:.2f} sensitivity to broad index moves",
        ),
        RiskFactorBreakdown(
            factor_name="Price Instability & Divergence",
            raw_value=round(base_m.price_instability, 2),
            normalized_score=round(instability_score, 1),
            weight=0.10,
            contribution=round(instability_score * 0.10, 2),
            interpretation=f"{base_m.price_instability:.2f} recent-to-long term volatility ratio",
        ),
    ]

    overall_score = round(sum(f.contribution for f in factors), 1)
    classification, color = _classify_risk(overall_score)

    # Identify primary risk drivers
    drivers: list[str] = []
    if base_m.annualized_volatility > 0.30:
        drivers.append(f"Elevated annual volatility ({base_m.annualized_volatility * 100:.1f}%)")
    elif base_m.annualized_volatility < 0.18:
        drivers.append(f"Stable low volatility ({base_m.annualized_volatility * 100:.1f}%)")

    if base_m.max_drawdown > 0.25:
        drivers.append(f"Deep maximum drawdown (-{base_m.max_drawdown * 100:.1f}%)")

    if base_m.beta > 1.20:
        drivers.append(f"High market sensitivity (Beta {base_m.beta:.2f})")
    elif base_m.beta < 0.80:
        drivers.append(f"Defensive lower market beta ({base_m.beta:.2f})")

    if base_m.price_instability > 1.25:
        drivers.append(
            f"Accelerating short-term volatility (Ratio {base_m.price_instability:.2f}x)"
        )

    if sector_divergence_info and abs(sector_divergence_info[0]) > 2.0:
        z_score = sector_divergence_info[0]
        status = sector_divergence_info[1]
        drivers.append(f"Extreme sector divergence ({z_score:+.2f}σ, {status})")

    if not drivers:
        drivers.append("Balanced market risk profile across all core metrics")

    # Dynamic explainable narrative (NO hardcoded stock names)
    explanation_parts: list[str] = [f"Assessed as {classification} Risk ({overall_score:.0f}/100)."]
    if base_m.annualized_volatility > 0.28:
        vol_pct = base_m.annualized_volatility * 100
        vol_contrib = vol_score * 0.30
        explanation_parts.append(
            f"Volatility is elevated at {vol_pct:.1f}% annualized, contributing "
            f"{vol_contrib:.1f} pts to the risk score."
        )
    if base_m.max_drawdown > 0.20:
        explanation_parts.append(
            f"Experienced a maximum drawdown of -{base_m.max_drawdown * 100:.1f}% "
            f"over the lookback window."
        )
    if base_m.beta > 1.15:
        swing_amp = (base_m.beta - 1.0) * 100
        explanation_parts.append(
            f"Beta of {base_m.beta:.2f} indicates that price swings tend to be amplified "
            f"by {swing_amp:.0f}% relative to NIFTY 50."
        )
    elif base_m.beta < 0.85:
        explanation_parts.append(
            f"Beta of {base_m.beta:.2f} provides defensive resilience "
            f"against broad market pullbacks."
        )
    narrative_explanation = " ".join(explanation_parts)

    # ─── Since-Purchase Performance & Risk (if holding info available) ───
    purchase_price = (
        float(holding_info["buyPrice"]) if (holding_info and holding_info.get("buyPrice")) else None
    )
    current_price = float(prices_series.iloc[-1]) if not prices_series.empty else None
    buy_date_str = holding_info.get("buyDate") if holding_info else None
    quantity = float(holding_info.get("quantity", 0)) if holding_info else 0.0

    unrealized_return = None
    unrealized_pnl = None
    drawdown_since_purchase = None
    vol_since_purchase = None

    if purchase_price and current_price and purchase_price > 0:
        unrealized_return = round(
            float((current_price - purchase_price) / purchase_price * 100.0), 2
        )
        if quantity > 0:
            unrealized_pnl = round(float((current_price - purchase_price) * quantity), 2)

    if buy_date_str:
        try:
            buy_date = date.fromisoformat(buy_date_str)
            since_purchase_series = prices_series[prices_series.index >= buy_date]
            if len(since_purchase_series) >= 2:
                since_ret = np.log(since_purchase_series / since_purchase_series.shift(1)).dropna()
                vol_since_purchase = round(
                    float(np.std(since_ret, ddof=1) * math.sqrt(ANNUALISATION_FACTOR) * 100), 2
                )

                peak = np.maximum.accumulate(since_purchase_series.to_numpy())
                dd_arr = since_purchase_series.to_numpy() / peak - 1.0
                drawdown_since_purchase = round(float(abs(np.min(dd_arr)) * 100), 2)
        except Exception:
            pass

    # Recent risk change: compare 1M vol to 6M vol
    if (
        windows_metrics["1M"].annualized_volatility
        > windows_metrics["6M"].annualized_volatility * 1.15
    ):
        recent_risk_change = "increasing"
    elif (
        windows_metrics["1M"].annualized_volatility
        < windows_metrics["6M"].annualized_volatility * 0.85
    ):
        recent_risk_change = "decreasing"
    else:
        recent_risk_change = "stable"

    sector_residual: float | None = None
    if (
        sector_divergence_info
        and len(sector_divergence_info) >= 3
        and sector_divergence_info[2] is not None
    ):
        sector_residual = round(float(sector_divergence_info[2]), 4)

    return StockRiskProfile(
        symbol=symbol,
        company_name=str(holding_info.get("companyName", symbol)) if holding_info else symbol,
        sector=str(holding_info.get("sector", "General")) if holding_info else "General",
        weight=round(float(holding_info.get("weight", 0.0)), 4) if holding_info else 0.0,
        overall_score=overall_score,
        risk_classification=classification,
        color=color,
        primary_drivers=drivers,
        narrative_explanation=narrative_explanation,
        factors=factors,
        windows=windows_metrics,
        purchase_price=round(purchase_price, 2) if purchase_price else None,
        current_price=round(current_price, 2) if current_price else None,
        unrealized_pnl=unrealized_pnl,
        unrealized_return=unrealized_return,
        drawdown_since_purchase=drawdown_since_purchase,
        volatility_since_purchase=vol_since_purchase,
        recent_risk_change=recent_risk_change,
        sector_divergence_20d=round(float(sector_divergence_info[0]), 2)
        if sector_divergence_info
        else None,
        sector_divergence_band=sector_divergence_info[1] if sector_divergence_info else None,
        sector_relative_performance=sector_residual,
        benchmark_relative_performance=base_m.excess_return,
        data_coverage=f"{base_m.observations} daily returns ({base_m.window})",
    )


def calculate_portfolio_comprehensive_risk(
    holdings: list[dict[str, Any]],
    session: Session,
) -> tuple[list[StockRiskProfile], PortfolioRiskProfile]:
    """Calculate stock-level risk profiles and full portfolio-level covariance
    and diversification metrics.
    """
    if not holdings:
        empty_profile = PortfolioRiskProfile(
            portfolio_risk_score=0.0,
            portfolio_classification="Low",
            portfolio_color="#2e7d32",
            annualized_volatility=0.0,
            downside_volatility=0.0,
            max_drawdown=0.0,
            portfolio_beta=1.0,
            holding_hhi=0.0,
            effective_holdings=0.0,
            sector_hhi=0.0,
            effective_sectors=0.0,
            diversification_ratio=1.0,
            diversification_score=0.0,
            diversification_grade="D",
            diversification_interpretation="No active holdings.",
            risk_contributions=[],
            sector_exposure=[],
            correlation_matrix={},
            historical_risk_trend="stable",
            summary_findings=["No active holdings in portfolio."],
        )
        return [], empty_profile

    symbols = [h["symbol"].upper() for h in holdings]
    weights_raw = np.array(
        [float(h.get("quantity", 1)) * float(h.get("buyPrice", 1)) for h in holdings], dtype=float
    )
    total_val = float(np.sum(weights_raw))
    weights = weights_raw / total_val if total_val > 0 else np.ones(len(holdings)) / len(holdings)

    # 1. Fetch benchmark returns
    bench_returns = get_benchmark_returns()

    # 2. Fetch prices: first from DB, fallback to yfinance
    prices_df = _load_stock_prices_from_db(session, symbols, days=380)
    missing_symbols = [
        s for s in symbols if s not in prices_df.columns or len(prices_df[s].dropna()) < 30
    ]
    if missing_symbols:
        yf_prices = _load_stock_prices_yfinance(missing_symbols)
        if not yf_prices.empty:
            for s in missing_symbols:
                if s in yf_prices.columns:
                    prices_df[s] = yf_prices[s]

    # Fill remaining missing with single-stock fetch
    for s in symbols:
        if s not in prices_df.columns or len(prices_df[s].dropna()) < 10:
            raw_s, yf_s = normalize_symbol_for_yahoo(s)
            try:
                hist = yf.Ticker(yf_s).history(period="1y", interval="1d", auto_adjust=False)
                if not hist.empty:
                    series = hist["Adj Close"].dropna()
                    series.index = pd.to_datetime(series.index).tz_localize(None).date
                    prices_df[s] = series
            except Exception:
                pass

    # 3. Fetch Layer 1 sector divergence scores for held stocks
    sector_divergence_scores: dict[str, tuple[float, str, float | None]] = {}
    try:
        from backend.app.db.models import SectorDivergenceScore

        latest_run = session.scalar(latest_completed_run_query())
        if latest_run:
            scores_rows = session.scalars(
                select(SectorDivergenceScore).where(
                    SectorDivergenceScore.run_id == latest_run.id,
                    SectorDivergenceScore.horizon == 20,
                    SectorDivergenceScore.symbol.in_(symbols),
                )
            ).all()
            for r in scores_rows:
                sector_divergence_scores[r.symbol] = (
                    float(r.divergence_value),
                    r.interpretation,
                    float(r.residual_value) if r.residual_value is not None else None,
                )
    except Exception:
        pass

    # 4. Compute stock risk profiles
    stock_profiles: list[StockRiskProfile] = []
    holding_map = {h["symbol"].upper(): h for h in holdings}

    for idx, sym in enumerate(symbols):
        if sym in prices_df.columns and len(prices_df[sym].dropna()) >= 10:
            prices_series = prices_df[sym].dropna()
        else:
            # Fallback price series if totally missing from DB and API
            dates = [date.today() - timedelta(days=i) for i in range(120, 0, -1)]
            prices_series = pd.Series([100.0 * (1 + 0.0005 * i) for i in range(120)], index=dates)

        h_info = holding_map.get(sym, {})
        h_info_with_weight = {**h_info, "weight": float(weights[idx])}
        profile = calculate_stock_risk(
            symbol=sym,
            prices_series=prices_series,
            benchmark_returns=bench_returns,
            holding_info=h_info_with_weight,
            sector_divergence_info=sector_divergence_scores.get(sym),
        )
        stock_profiles.append(profile)

    # 5. Portfolio Covariance and Return Metrics
    common_prices = prices_df[[s for s in symbols if s in prices_df.columns]].dropna()
    historical_risk_trend = "stable"

    if len(common_prices) >= 20 and len(common_prices.columns) == len(symbols):
        returns_matrix = np.log(common_prices / common_prices.shift(1)).dropna()
        cov_daily = np.cov(returns_matrix.to_numpy(), rowvar=False, ddof=1)
        if len(symbols) == 1:
            cov_daily = np.array([[float(cov_daily)]])
        cov_annual = cov_daily * ANNUALISATION_FACTOR

        sigma_w = cov_annual @ weights
        port_var = float(weights @ sigma_w)
        port_vol = float(math.sqrt(max(port_var, 0.0)))

        port_returns = returns_matrix.to_numpy() @ weights
        neg_returns = np.minimum(port_returns, 0.0)
        port_downside = float(
            math.sqrt(np.mean(np.square(neg_returns))) * math.sqrt(ANNUALISATION_FACTOR)
        )

        wealth = np.exp(np.cumsum(port_returns))
        peaks = np.maximum.accumulate(wealth)
        port_drawdown = float(abs(np.min(wealth / peaks - 1.0)))

        # Euler Risk Contributions: (w_i * (Sigma w)_i) / port_var
        risk_contributions: list[dict[str, Any]] = []
        for i, sym in enumerate(symbols):
            rc = (
                float(weights[i] * sigma_w[i] / max(port_var, 1e-8))
                if port_var > 1e-8
                else float(weights[i])
            )
            risk_contributions.append(
                {
                    "symbol": sym,
                    "weight": round(float(weights[i]), 4),
                    "annualized_volatility": round(float(math.sqrt(max(cov_annual[i, i], 0.0))), 4),
                    "risk_contribution_share": round(float(rc * 100.0), 2),
                    "marginal_risk": round(float(sigma_w[i] / max(port_vol, 1e-8)), 4),
                }
            )

        # Correlation Matrix
        stds = np.sqrt(np.diag(cov_annual))
        outer_stds = np.outer(stds, stds)
        corr_matrix_np = np.divide(
            cov_annual, outer_stds, out=np.zeros_like(cov_annual), where=outer_stds != 0
        )
        corr_dict: dict[str, dict[str, float]] = {}
        for r_i, s_r in enumerate(symbols):
            corr_dict[s_r] = {}
            for c_i, s_c in enumerate(symbols):
                corr_dict[s_r][s_c] = round(float(corr_matrix_np[r_i, c_i]), 3)

        # Diversification Ratio = weighted vol sum / portfolio vol
        weighted_vol_sum = float(np.sum(weights * stds))
        diversification_ratio = float(weighted_vol_sum / max(port_vol, 0.01))

        # Historical risk trend comparison: 1M (21d) vs longer window (63d / 126d)
        if len(returns_matrix) >= 21:
            r_1m = returns_matrix.iloc[-21:].to_numpy() @ weights
            vol_1m = float(np.std(r_1m, ddof=1) * math.sqrt(ANNUALISATION_FACTOR))
            lookback_len = min(len(returns_matrix), 126)
            if lookback_len >= 42:
                r_long = returns_matrix.iloc[-lookback_len:].to_numpy() @ weights
                vol_long = float(np.std(r_long, ddof=1) * math.sqrt(ANNUALISATION_FACTOR))
                if vol_1m > vol_long * 1.15:
                    historical_risk_trend = "increasing"
                elif vol_1m < vol_long * 0.85:
                    historical_risk_trend = "decreasing"
    else:
        # Fallback if price overlap is insufficient
        port_vol = float(
            np.sum([p.windows["1Y"].annualized_volatility * p.weight for p in stock_profiles])
        )
        port_downside = float(
            np.sum([p.windows["1Y"].downside_volatility * p.weight for p in stock_profiles])
        )
        port_drawdown = (
            float(np.max([p.windows["1Y"].max_drawdown for p in stock_profiles]))
            if stock_profiles
            else 0.15
        )
        diversification_ratio = 1.05
        risk_contributions = [
            {
                "symbol": p.symbol,
                "weight": round(float(p.weight), 4),
                "annualized_volatility": round(float(p.windows["1Y"].annualized_volatility), 4),
                "risk_contribution_share": round(float(p.weight * 100.0), 2),
                "marginal_risk": round(float(p.windows["1Y"].annualized_volatility), 4),
            }
            for p in stock_profiles
        ]
        corr_dict = {
            p.symbol: {
                other.symbol: 1.0 if p.symbol == other.symbol else 0.5 for other in stock_profiles
            }
            for p in stock_profiles
        }

    # Portfolio Beta (weighted sum of stock betas)
    port_beta = float(np.sum([p.windows["1Y"].beta * p.weight for p in stock_profiles]))

    # Concentration metrics
    holding_hhi = float(np.sum(weights**2))
    effective_holdings = float(1.0 / max(holding_hhi, 1e-6))

    # Sector Breakdown
    sector_weights: dict[str, float] = {}
    sector_risk_shares: dict[str, float] = {}
    for p in stock_profiles:
        sec = p.sector or "General"
        sector_weights[sec] = sector_weights.get(sec, 0.0) + p.weight
        rc_val = next(
            (
                rc["risk_contribution_share"]
                for rc in risk_contributions
                if rc["symbol"] == p.symbol
            ),
            p.weight * 100,
        )
        sector_risk_shares[sec] = sector_risk_shares.get(sec, 0.0) + rc_val

    sector_hhi = float(sum(w**2 for w in sector_weights.values()))
    effective_sectors = float(1.0 / max(sector_hhi, 1e-6))

    # Prudent benchmark allocation target: 25% single sector ceiling
    SECTOR_BENCHMARK_TARGET = 25.0
    sector_exposure_list = []
    for sec, w in sorted(sector_weights.items(), key=lambda item: -item[1]):
        weight_pct = round(float(w * 100.0), 2)
        if weight_pct > 35.0:
            status = "Excessive"
        elif weight_pct > SECTOR_BENCHMARK_TARGET:
            status = "Elevated"
        else:
            status = "Balanced"

        sec_stocks = [p for p in stock_profiles if (p.sector or "General") == sec]
        avg_div = [
            p.sector_divergence_20d for p in sec_stocks if p.sector_divergence_20d is not None
        ]
        avg_divergence = round(float(np.mean(avg_div)), 2) if avg_div else None

        sector_exposure_list.append(
            {
                "sector": sec,
                "weight": weight_pct,
                "benchmark_target": SECTOR_BENCHMARK_TARGET,
                "allocation_status": status,
                "risk_contribution_share": round(float(sector_risk_shares.get(sec, weight_pct)), 2),
                "stock_count": len(sec_stocks),
                "stocks": [p.symbol for p in sec_stocks],
                "average_sector_divergence": avg_divergence,
            }
        )

    # 6. Overall Portfolio Risk Score (0–100)
    p_vol_score = _normalize_factor(port_vol, 0.10, 0.35)
    p_down_score = _normalize_factor(port_downside, 0.06, 0.25)
    p_dd_score = _normalize_factor(port_drawdown, 0.08, 0.38)
    p_beta_score = float(np.clip(50.0 + (port_beta - 1.0) * 55.0, 0.0, 100.0))

    portfolio_risk_score = round(
        0.35 * p_vol_score + 0.25 * p_down_score + 0.25 * p_dd_score + 0.15 * p_beta_score, 1
    )
    port_class, port_color = _classify_risk(portfolio_risk_score)

    # 7. Diversification Score (0–100, HIGHER is MORE diversified)
    # Component A: Effective holdings ratio (up to 100)
    score_holdings = min(100.0, (effective_holdings / max(len(symbols), 1)) * 100.0)
    # Component B: Sector spread (5+ sectors is full marks)
    score_sectors = min(100.0, (effective_sectors / 5.0) * 100.0)
    # Component C: Correlation benefit (DR > 1.0)
    score_dr = float(np.clip(35.0 + (diversification_ratio - 1.0) * 120.0, 0.0, 100.0))

    diversification_score = round(0.35 * score_holdings + 0.35 * score_sectors + 0.30 * score_dr, 1)
    if diversification_score >= 80:
        div_grade: DiversificationGrade = "A"
        div_interp = "Well diversified across non-correlated equities and multi-sector exposure."
    elif diversification_score >= 60:
        div_grade = "B"
        div_interp = (
            "Moderately diversified. Moderate co-movement with modest sector concentration."
        )
    elif diversification_score >= 40:
        div_grade = "C"
        div_interp = "Concentrated portfolio. A few dominant positions drive the majority of risk."
    else:
        div_grade = "D"
        div_interp = (
            "Highly concentrated. Strong co-movement exposes the portfolio to single-sector shocks."
        )

    # Findings
    findings: list[str] = []
    if port_beta > 1.15:
        findings.append(
            f"Portfolio Beta of {port_beta:.2f} indicates elevated market exposure vs NIFTY 50."
        )
    elif port_beta < 0.85:
        findings.append(
            f"Defensive Portfolio Beta of {port_beta:.2f} provides downside insulation."
        )

    if effective_sectors < 2.5:
        top_sec = sector_exposure_list[0] if sector_exposure_list else None
        if top_sec:
            sec_name = top_sec["sector"]
            sec_wt = top_sec["weight"]
            sec_status = top_sec["allocation_status"]
            findings.append(
                f"Sector risk concentration: {sec_name} comprises {sec_wt}% "
                f"of total capital ({sec_status})."
            )

    if diversification_ratio > 1.25:
        vol_red = (1 - 1 / diversification_ratio) * 100
        findings.append(
            f"Solid diversification benefit: portfolio volatility is {vol_red:.1f}% "
            f"lower than weighted individual asset volatility."
        )

    portfolio_profile = PortfolioRiskProfile(
        portfolio_risk_score=portfolio_risk_score,
        portfolio_classification=port_class,
        portfolio_color=port_color,
        annualized_volatility=round(port_vol * 100.0, 2),
        downside_volatility=round(port_downside * 100.0, 2),
        max_drawdown=round(port_drawdown * 100.0, 2),
        portfolio_beta=round(port_beta, 2),
        holding_hhi=round(holding_hhi, 4),
        effective_holdings=round(effective_holdings, 2),
        sector_hhi=round(sector_hhi, 4),
        effective_sectors=round(effective_sectors, 2),
        diversification_ratio=round(diversification_ratio, 2),
        diversification_score=diversification_score,
        diversification_grade=div_grade,
        diversification_interpretation=div_interp,
        risk_contributions=risk_contributions,
        sector_exposure=sector_exposure_list,
        correlation_matrix=corr_dict,
        historical_risk_trend=historical_risk_trend,
        summary_findings=findings,
    )

    return stock_profiles, portfolio_profile
