"""Fundamental metrics and TTM ratio calculations with point-in-time rules."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.model_config import FundamentalAnalysisConfig
from backend.app.db.models import FundamentalMetric, FundamentalPeriod, Security

logger = logging.getLogger(__name__)


@dataclass
class CalculatedMetric:
    metric_key: str
    value: float | None
    source_period_end: date | None
    data_age_days: int | None
    peer_group: str
    status: str  # "computed" | "missing" | "insufficient" | "flagged"
    details: dict[str, Any]


def get_usable_periods(
    session: Session,
    security_id: UUID,
    as_of: date | datetime,
    basis_preference: str = "consolidated",
) -> list[FundamentalPeriod]:
    """Retrieve all fundamental periods strictly published on or before as_of.

    Point-in-time guarantees:
    - Only rows with published_at <= as_of are visible.
    - If multiple versions exist for the same period_end and basis, only the
      latest version published before as_of is retained.
    - Selects preferred basis (e.g. consolidated) if available, falling back to
      standalone or unknown.
    """
    cutoff = (
        as_of
        if isinstance(as_of, datetime)
        else datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59, tzinfo=UTC)
    )

    stmt = (
        select(FundamentalPeriod)
        .where(
            FundamentalPeriod.security_id == security_id,
            FundamentalPeriod.published_at <= cutoff,
        )
        .order_by(
            FundamentalPeriod.period_end.desc(),
            FundamentalPeriod.version.desc(),
        )
    )
    rows = session.scalars(stmt).all()

    # Filter to highest version per (period_end, basis, period_type)
    deduped: dict[tuple[date, str, str], FundamentalPeriod] = {}
    for r in rows:
        key = (r.period_end, r.basis, r.period_type)
        if key not in deduped:
            deduped[key] = r

    # For each period_end and period_type, select preferred basis
    grouped: dict[tuple[date, str], list[FundamentalPeriod]] = {}
    for p in deduped.values():
        grouped.setdefault((p.period_end, p.period_type), []).append(p)

    selected: list[FundamentalPeriod] = []
    for periods_for_date in grouped.values():
        # Preference: consolidated -> standalone -> unknown
        chosen = next((p for p in periods_for_date if p.basis == basis_preference), None)
        if chosen is None:
            chosen = next((p for p in periods_for_date if p.basis == "standalone"), None)
        if chosen is None:
            chosen = periods_for_date[0]
        selected.append(chosen)

    # Sort chronological by period_end ascending
    selected.sort(key=lambda p: p.period_end)
    return selected


def compute_ttm_metrics(
    security: Security,
    periods: list[FundamentalPeriod],
    as_of: date,
    config: FundamentalAnalysisConfig,
) -> list[CalculatedMetric]:
    """Compute point-in-time TTM ratios and metrics per peer-group profile."""
    industry = security.industry or security.sector or "General"
    is_financial = any(
        fin.lower() in (security.sector or "").lower()
        or fin.lower() in (security.industry or "").lower()
        for fin in config.financial_sectors
    )
    peer_group = industry

    # Filter to quarterly periods
    quarters = [p for p in periods if p.period_type == "quarter"]
    if not quarters:
        # No published results exist
        keys = (
            ["asset_to_equity", "profit_growth", "profit_volatility"]
            if is_financial
            else [
                "debt_to_equity",
                "interest_coverage",
                "ttm_profit_growth",
                "profit_volatility",
                "cash_flow_quality",
                "margin_trend",
            ]
        )
        return [
            CalculatedMetric(
                metric_key=k,
                value=None,
                source_period_end=None,
                data_age_days=None,
                peer_group=peer_group,
                status="missing",
                details={"reason": "no_published_quarters"},
            )
            for k in keys
        ]

    latest_quarter = quarters[-1]
    data_age_days = (as_of - latest_quarter.period_end).days

    results: list[CalculatedMetric] = []
    quality_flags: list[str] = []

    # Quality check: negative equity
    latest_equity = latest_quarter.total_equity
    if latest_equity is not None and latest_equity <= 0:
        quality_flags.append("negative_equity")

    # Flow items require trailing 4 quarters
    has_ttm = len(quarters) >= 4
    t4_quarters = quarters[-4:] if has_ttm else quarters

    ttm_pat = (
        sum(p.pat for p in t4_quarters if p.pat is not None)
        if has_ttm and all(p.pat is not None for p in t4_quarters)
        else None
    )
    ttm_revenue = (
        sum(p.revenue for p in t4_quarters if p.revenue is not None)
        if has_ttm and all(p.revenue is not None for p in t4_quarters)
        else None
    )
    ttm_op = (
        sum(p.operating_profit for p in t4_quarters if p.operating_profit is not None)
        if has_ttm and all(p.operating_profit is not None for p in t4_quarters)
        else None
    )
    ttm_interest = (
        sum(p.interest_expense for p in t4_quarters if p.interest_expense is not None)
        if has_ttm and all(p.interest_expense is not None for p in t4_quarters)
        else None
    )
    ttm_cfo = (
        sum(p.cash_from_operations for p in t4_quarters if p.cash_from_operations is not None)
        if has_ttm and all(p.cash_from_operations is not None for p in t4_quarters)
        else None
    )

    # Balance sheet items (latest)
    latest_debt = latest_quarter.total_debt
    latest_assets = latest_quarter.total_assets

    if is_financial:
        # === Financials / Banks Profile ===
        # 1. Asset to Equity (Leverage proxy for banks)
        if latest_assets is not None and latest_equity is not None and latest_equity > 0:
            a_to_e = latest_assets / latest_equity
            results.append(
                CalculatedMetric(
                    metric_key="asset_to_equity",
                    value=round(a_to_e, 4),
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="flagged" if quality_flags else "computed",
                    details={"flags": quality_flags, "basis": latest_quarter.basis},
                )
            )
        else:
            results.append(
                CalculatedMetric(
                    metric_key="asset_to_equity",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="missing",
                    details={"reason": "missing_assets_or_equity"},
                )
            )

        # 2. Profit growth (YoY TTM PAT growth)
        # Requires at least 5 quarters (trailing 4 vs trailing 4 of prior year)
        if len(quarters) < config.ttm_min_quarters_for_yoy:
            results.append(
                CalculatedMetric(
                    metric_key="profit_growth",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="insufficient",
                    details={
                        "quarters_available": len(quarters),
                        "min_required": config.ttm_min_quarters_for_yoy,
                    },
                )
            )
        else:
            # Prev year TTM PAT
            prev_t4 = quarters[-8:-4] if len(quarters) >= 8 else [quarters[-5]]
            prev_pat = sum(p.pat for p in prev_t4 if p.pat is not None)
            if ttm_pat is not None and prev_pat and abs(prev_pat) > 1e-4:
                growth = (ttm_pat - prev_pat) / abs(prev_pat)
                results.append(
                    CalculatedMetric(
                        metric_key="profit_growth",
                        value=round(growth, 4),
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="computed",
                        details={"ttm_pat": ttm_pat, "prev_pat": prev_pat},
                    )
                )
            else:
                results.append(
                    CalculatedMetric(
                        metric_key="profit_growth",
                        value=None,
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="missing",
                        details={"reason": "zero_or_missing_base_pat"},
                    )
                )

        # 3. Profit Volatility (std of quarterly PAT)
        pats = [p.pat for p in quarters[-4:] if p.pat is not None]
        if len(pats) >= 3:
            std_pat = float(np.std(pats, ddof=1))
            mean_pat = abs(float(np.mean(pats))) if abs(float(np.mean(pats))) > 1e-4 else 1.0
            vol = std_pat / mean_pat
            results.append(
                CalculatedMetric(
                    metric_key="profit_volatility",
                    value=round(vol, 4),
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="computed",
                    details={"quarterly_pats": pats},
                )
            )
        else:
            results.append(
                CalculatedMetric(
                    metric_key="profit_volatility",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="insufficient",
                    details={"quarters_with_pat": len(pats)},
                )
            )

        # Report missing bank-specific items
        for missing_item in ["gross_npa_pct", "net_npa_pct", "capital_adequacy_ratio"]:
            results.append(
                CalculatedMetric(
                    metric_key=missing_item,
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="missing",
                    details={"reason": "not_disclosed_in_standard_feed"},
                )
            )

    else:
        # === Non-Financials Profile ===
        # 1. Debt to Equity
        if latest_debt is not None and latest_equity is not None:
            if latest_equity <= 0:
                results.append(
                    CalculatedMetric(
                        metric_key="debt_to_equity",
                        value=999.0,  # Extreme leverage indicator
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="flagged",
                        details={"reason": "negative_or_zero_equity", "equity": latest_equity},
                    )
                )
            else:
                d_to_e = latest_debt / latest_equity
                results.append(
                    CalculatedMetric(
                        metric_key="debt_to_equity",
                        value=round(d_to_e, 4),
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="computed",
                        details={"debt": latest_debt, "equity": latest_equity},
                    )
                )
        else:
            results.append(
                CalculatedMetric(
                    metric_key="debt_to_equity",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="missing",
                    details={"reason": "missing_debt_or_equity"},
                )
            )

        # 2. Interest Coverage (EBIT / Interest Expense)
        if ttm_op is not None and ttm_interest is not None:
            if ttm_interest <= 0:
                # Virtually debt-free or zero interest expense
                results.append(
                    CalculatedMetric(
                        metric_key="interest_coverage",
                        value=100.0,  # High safe coverage
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="computed",
                        details={"note": "zero_or_negligible_interest_expense"},
                    )
                )
            else:
                ic = ttm_op / ttm_interest
                results.append(
                    CalculatedMetric(
                        metric_key="interest_coverage",
                        value=round(ic, 4),
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="flagged" if ic < 1.0 else "computed",
                        details={"operating_profit_ttm": ttm_op, "interest_ttm": ttm_interest},
                    )
                )
        else:
            results.append(
                CalculatedMetric(
                    metric_key="interest_coverage",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="missing",
                    details={"reason": "missing_operating_profit_or_interest"},
                )
            )

        # 3. TTM Profit Growth (YoY)
        if len(quarters) < config.ttm_min_quarters_for_yoy:
            results.append(
                CalculatedMetric(
                    metric_key="ttm_profit_growth",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="insufficient",
                    details={
                        "quarters_available": len(quarters),
                        "min_required": config.ttm_min_quarters_for_yoy,
                    },
                )
            )
        else:
            prev_t4 = quarters[-8:-4] if len(quarters) >= 8 else [quarters[-5]]
            prev_pat = sum(p.pat for p in prev_t4 if p.pat is not None)
            if ttm_pat is not None and prev_pat and abs(prev_pat) > 1e-4:
                growth = (ttm_pat - prev_pat) / abs(prev_pat)
                results.append(
                    CalculatedMetric(
                        metric_key="ttm_profit_growth",
                        value=round(growth, 4),
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="computed",
                        details={"ttm_pat": ttm_pat, "prev_pat": prev_pat},
                    )
                )
            else:
                results.append(
                    CalculatedMetric(
                        metric_key="ttm_profit_growth",
                        value=None,
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="missing",
                        details={"reason": "zero_or_missing_base_pat"},
                    )
                )

        # 4. Profit Volatility
        pats = [p.pat for p in quarters[-4:] if p.pat is not None]
        if len(pats) >= 3:
            std_pat = float(np.std(pats, ddof=1))
            mean_pat = abs(float(np.mean(pats))) if abs(float(np.mean(pats))) > 1e-4 else 1.0
            vol = std_pat / mean_pat
            results.append(
                CalculatedMetric(
                    metric_key="profit_volatility",
                    value=round(vol, 4),
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="computed",
                    details={"quarterly_pats": pats},
                )
            )
        else:
            results.append(
                CalculatedMetric(
                    metric_key="profit_volatility",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="insufficient",
                    details={"quarters_with_pat": len(pats)},
                )
            )

        # 5. Cash Flow Quality (CFO / PAT)
        if ttm_cfo is not None and ttm_pat is not None:
            if abs(ttm_pat) < 1e-4:
                cfq = 1.0 if ttm_cfo >= 0 else -1.0
            else:
                cfq = ttm_cfo / ttm_pat
            results.append(
                CalculatedMetric(
                    metric_key="cash_flow_quality",
                    value=round(cfq, 4),
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="computed",
                    details={"ttm_cfo": ttm_cfo, "ttm_pat": ttm_pat},
                )
            )
        else:
            results.append(
                CalculatedMetric(
                    metric_key="cash_flow_quality",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="missing",
                    details={"reason": "missing_cfo_or_pat"},
                )
            )

        # 6. Margin Trend (Operating Margin current TTM vs prev TTM)
        if ttm_op is not None and ttm_revenue is not None and ttm_revenue > 0:
            current_margin = ttm_op / ttm_revenue
            # Prev margin
            prev_t4 = quarters[-8:-4] if len(quarters) >= 8 else []
            if prev_t4 and all(p.revenue and p.operating_profit is not None for p in prev_t4):
                prev_rev = sum(p.revenue for p in prev_t4 if p.revenue)
                prev_op = sum(p.operating_profit for p in prev_t4 if p.operating_profit is not None)
                if prev_rev > 0:
                    prev_margin = prev_op / prev_rev
                    trend = current_margin - prev_margin
                    results.append(
                        CalculatedMetric(
                            metric_key="margin_trend",
                            value=round(trend, 4),
                            source_period_end=latest_quarter.period_end,
                            data_age_days=data_age_days,
                            peer_group=peer_group,
                            status="computed",
                            details={"current_margin": current_margin, "prev_margin": prev_margin},
                        )
                    )
                else:
                    results.append(
                        CalculatedMetric(
                            metric_key="margin_trend",
                            value=round(current_margin, 4),
                            source_period_end=latest_quarter.period_end,
                            data_age_days=data_age_days,
                            peer_group=peer_group,
                            status="computed",
                            details={"current_margin": current_margin},
                        )
                    )
            else:
                results.append(
                    CalculatedMetric(
                        metric_key="margin_trend",
                        value=round(current_margin, 4),
                        source_period_end=latest_quarter.period_end,
                        data_age_days=data_age_days,
                        peer_group=peer_group,
                        status="computed",
                        details={"current_margin": current_margin},
                    )
                )
        else:
            results.append(
                CalculatedMetric(
                    metric_key="margin_trend",
                    value=None,
                    source_period_end=latest_quarter.period_end,
                    data_age_days=data_age_days,
                    peer_group=peer_group,
                    status="missing",
                    details={"reason": "missing_revenue_or_operating_profit"},
                )
            )

    return results


def save_fundamental_metrics(
    session: Session,
    security_id: UUID,
    as_of: date,
    metrics: list[CalculatedMetric],
) -> list[FundamentalMetric]:
    """Upsert calculated metrics for a security and as_of date."""
    saved: list[FundamentalMetric] = []
    for m in metrics:
        stmt = select(FundamentalMetric).where(
            FundamentalMetric.security_id == security_id,
            FundamentalMetric.as_of == as_of,
            FundamentalMetric.metric_key == m.metric_key,
            FundamentalMetric.peer_group == m.peer_group,
        )
        existing = session.scalars(stmt).first()
        if existing:
            existing.value = m.value
            existing.source_period_end = m.source_period_end
            existing.data_age_days = m.data_age_days
            existing.status = m.status
            existing.details = m.details
            saved.append(existing)
        else:
            row = FundamentalMetric(
                security_id=security_id,
                as_of=as_of,
                metric_key=m.metric_key,
                value=m.value,
                source_period_end=m.source_period_end,
                data_age_days=m.data_age_days,
                peer_group=m.peer_group,
                status=m.status,
                details=m.details,
            )
            session.add(row)
            saved.append(row)

    session.flush()
    return saved
