"""Governance metrics — point-in-time computation of shareholding and insider signals.

All computations are purely descriptive (no look-ahead, no prediction).
Every function takes an explicit `as_of` cutoff and only uses data with
published_at <= as_of (D4).

Formulas:
  pledge_level      = promoter_pledged_pct_of_promoter (latest quarter visible)
  pledge_change     = pledge_level_t - pledge_level_t-N (N = config.min_quarters_for_change)
  promoter_change   = promoter_pct_t - promoter_pct_t-N
  institutional_change = (fii_pct + dii_pct)_t - (fii_pct + dii_pct)_t-N
  insider_net_sell_value = SUM(value for sell) - SUM(value for buy) over window
  insider_sell_ratio = insider_net_sell_value / market_cap

Higher pledge / declining promoter / institutional outflow / net insider selling
→ higher risk (direction: higher_is_riskier for all four components).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.app.governance.config import GovernanceAnalysisConfig


@dataclass(frozen=True)
class PledgeMetrics:
    """Point-in-time pledge and promoter holding metrics."""

    quarter_end: date
    pledge_level: float | None  # % of promoter holding pledged
    pledge_change: float | None  # Δ% versus N quarters ago (None if insufficient history)
    promoter_pct: float | None  # Promoter % of total
    promoter_change: float | None  # Δ% promoter stake versus N quarters ago
    n_quarters_available: int
    status: str  # ok | missing | insufficient_history
    limitations: list[str]


@dataclass(frozen=True)
class InstitutionalFlowMetrics:
    """Point-in-time FII + DII combined holding change."""

    quarter_end: date
    fii_pct: float | None
    dii_pct: float | None
    combined_pct: float | None
    institutional_change: float | None  # Δ% (fii+dii) versus N quarters ago
    n_quarters_available: int
    status: str
    limitations: list[str]


@dataclass(frozen=True)
class InsiderActivityMetrics:
    """Net insider selling value over a rolling window relative to market cap."""

    window_days: int
    window_start: date
    window_end: date
    net_sell_value: float  # INR; positive = net selling
    buy_value: float
    sell_value: float
    trade_count: int
    insider_sell_ratio: float | None  # net_sell_value / market_cap; None if mktcap unknown
    status: str
    limitations: list[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sorted_quarters(
    patterns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return patterns sorted oldest-first by quarter_end, then by version desc.

    For the same quarter, keep only the highest-version row (latest restatement).
    """
    by_quarter: dict[date, dict[str, Any]] = {}
    for p in patterns:
        q: date = p["quarter_end"]
        existing = by_quarter.get(q)
        if existing is None or p.get("version", 1) > existing.get("version", 1):
            by_quarter[q] = p
    return sorted(by_quarter.values(), key=lambda r: r["quarter_end"])


# ---------------------------------------------------------------------------
# Public metric functions
# ---------------------------------------------------------------------------


def compute_pledge_metrics(
    patterns: list[dict[str, Any]],
    config: GovernanceAnalysisConfig,
) -> PledgeMetrics:
    """Compute pledge level, pledge change, and promoter holding change.

    Parameters
    ----------
    patterns:
        List of dicts (each representing one ShareholdingPattern row) that are
        already pre-filtered to only rows with published_at <= as_of.
        Required keys: quarter_end, version, promoter_pct,
                       promoter_pledged_pct_of_promoter
    config:
        Governance config loaded from model_config.
    """
    if not patterns:
        return PledgeMetrics(
            quarter_end=date.min,
            pledge_level=None,
            pledge_change=None,
            promoter_pct=None,
            promoter_change=None,
            n_quarters_available=0,
            status="missing",
            limitations=["No shareholding pattern data available for this security."],
        )

    sorted_pats = _sorted_quarters(patterns)
    latest = sorted_pats[-1]
    n_avail = len(sorted_pats)

    pledge_level = latest.get("promoter_pledged_pct_of_promoter")
    promoter_pct = latest.get("promoter_pct")

    limitations: list[str] = [
        "Shareholding pattern data from official SEBI/exchange filings via CSV import.",
        "Pledge % is as a fraction of promoter holding, not total shares.",
    ]

    # Compute 2-quarter change
    pledge_change: float | None = None
    promoter_change: float | None = None

    n_lookback = config.min_quarters_for_change
    if n_avail >= n_lookback:
        prior = sorted_pats[-n_lookback]
        prior_pledge = prior.get("promoter_pledged_pct_of_promoter")
        prior_promoter = prior.get("promoter_pct")

        if pledge_level is not None and prior_pledge is not None:
            pledge_change = round(pledge_level - prior_pledge, 4)
        if promoter_pct is not None and prior_promoter is not None:
            promoter_change = round(promoter_pct - prior_promoter, 4)
    else:
        limitations.append(
            f"Only {n_avail} quarter(s) available; {n_lookback} required for change computation."
        )

    status = "ok" if pledge_level is not None or promoter_pct is not None else "missing"
    return PledgeMetrics(
        quarter_end=latest["quarter_end"],
        pledge_level=pledge_level,
        pledge_change=pledge_change,
        promoter_pct=promoter_pct,
        promoter_change=promoter_change,
        n_quarters_available=n_avail,
        status=status,
        limitations=limitations,
    )


def compute_institutional_flow(
    patterns: list[dict[str, Any]],
    config: GovernanceAnalysisConfig,
) -> InstitutionalFlowMetrics:
    """Compute combined FII + DII holding change over config lookback.

    Parameters are the same as compute_pledge_metrics.
    Required keys: quarter_end, version, fii_pct, dii_pct
    """
    if not patterns:
        return InstitutionalFlowMetrics(
            quarter_end=date.min,
            fii_pct=None,
            dii_pct=None,
            combined_pct=None,
            institutional_change=None,
            n_quarters_available=0,
            status="missing",
            limitations=["No shareholding pattern data available."],
        )

    sorted_pats = _sorted_quarters(patterns)
    latest = sorted_pats[-1]
    n_avail = len(sorted_pats)

    fii = latest.get("fii_pct")
    dii = latest.get("dii_pct")
    combined = (fii or 0.0) + (dii or 0.0) if (fii is not None or dii is not None) else None

    limitations: list[str] = [
        "FII/DII split from SEBI Reg 31 disclosures — may not perfectly match exchange statistics.",
    ]

    institutional_change: float | None = None
    n_lookback = config.institutional_flow_lookback_quarters
    if n_avail >= n_lookback:
        prior = sorted_pats[-n_lookback]
        prior_fii = prior.get("fii_pct")
        prior_dii = prior.get("dii_pct")
        if combined is not None:
            prior_combined = (prior_fii or 0.0) + (prior_dii or 0.0)
            institutional_change = round(combined - prior_combined, 4)
    else:
        limitations.append(
            f"Only {n_avail} quarter(s) available; {n_lookback} required for change computation."
        )

    status = "ok" if combined is not None else "missing"
    return InstitutionalFlowMetrics(
        quarter_end=latest["quarter_end"],
        fii_pct=fii,
        dii_pct=dii,
        combined_pct=combined,
        institutional_change=institutional_change,
        n_quarters_available=n_avail,
        status=status,
        limitations=limitations,
    )


def compute_insider_activity(
    trades: list[dict[str, Any]],
    as_of: date,
    market_cap_inr: float | None,
    config: GovernanceAnalysisConfig,
) -> InsiderActivityMetrics:
    """Compute net insider selling value relative to market cap over rolling window.

    Parameters
    ----------
    trades:
        List of dicts (InsiderTrade rows) with keys:
        txn_type, value, txn_date, published_at.
        Already pre-filtered to published_at <= as_of.
    as_of:
        Signal computation date (trading calendar date).
    market_cap_inr:
        Current market cap in INR from security_market_stat.
        None if not available.
    config:
        Governance config.

    Net sell = SUM(value for sell) - SUM(value for buy).
    Pledges and revocations are excluded from the buy/sell calculation.
    """
    from datetime import timedelta

    window_start = as_of - timedelta(days=config.insider_window_days)

    # Filter to trades within the rolling window (txn_date basis)
    window_trades = [
        t
        for t in trades
        if t["txn_date"] >= window_start
        and t["txn_date"] <= as_of
        and t.get("txn_type") in {"buy", "sell"}
    ]

    buy_value = sum(
        float(t.get("value") or 0.0) for t in window_trades if t.get("txn_type") == "buy"
    )
    sell_value = sum(
        float(t.get("value") or 0.0) for t in window_trades if t.get("txn_type") == "sell"
    )
    net_sell = round(sell_value - buy_value, 2)

    limitations: list[str] = [
        "Insider trade data from SEBI PIT / SAST filings via CSV import.",
        "Net selling value uses disclosed INR amounts; unreported values are treated as 0.",
        "Pledge and revoke transactions are excluded from buy/sell netting.",
    ]

    insider_sell_ratio: float | None = None
    if (
        market_cap_inr is not None
        and market_cap_inr >= config.min_market_cap_inr
        and net_sell != 0.0
    ):
        insider_sell_ratio = round(net_sell / market_cap_inr, 8)
    elif market_cap_inr is None:
        limitations.append("Market cap not available; insider sell ratio not computed.")
    elif market_cap_inr < config.min_market_cap_inr:
        limitations.append(
            f"Market cap ({market_cap_inr:.0f} INR) is below the minimum threshold "
            f"({config.min_market_cap_inr:.0f} INR); sell ratio not computed."
        )

    status = "ok" if window_trades else "missing"

    return InsiderActivityMetrics(
        window_days=config.insider_window_days,
        window_start=window_start,
        window_end=as_of,
        net_sell_value=net_sell,
        buy_value=buy_value,
        sell_value=sell_value,
        trade_count=len(window_trades),
        insider_sell_ratio=insider_sell_ratio,
        status=status,
        limitations=limitations,
    )
