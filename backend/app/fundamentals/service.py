"""Service functions for stock fundamental data and peer percentiles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.model_config import FundamentalAnalysisConfig, load_model_config
from backend.app.db.models import (
    FundamentalMetric,
    Security,
    SecurityAlias,
)
from backend.app.fundamentals.metrics import compute_ttm_metrics, get_usable_periods


def get_stock_fundamentals(
    session: Session,
    symbol: str,
    as_of: datetime | None = None,
) -> dict[str, Any] | None:
    """Retrieve fundamental periods, derived TTM metrics, and peer percentiles for a stock."""
    norm_symbol = symbol.strip().upper()
    now_utc = as_of or datetime.now(UTC)

    # Resolve Security
    sec_alias = session.scalars(
        select(SecurityAlias).where(SecurityAlias.symbol == norm_symbol)
    ).first()
    if sec_alias is None:
        return None

    security = session.get(Security, sec_alias.security_id)
    if security is None:
        return None

    try:
        cfg_envelope = load_model_config(session, "fundamental_analysis", approved_only=False)
        config = FundamentalAnalysisConfig(**cfg_envelope.configuration)
    except Exception:
        config = FundamentalAnalysisConfig()

    periods = get_usable_periods(
        session,
        security_id=security.id,
        as_of=now_utc,
        basis_preference=config.default_basis_preference,
    )

    # Compute or fetch metrics
    metrics = compute_ttm_metrics(
        security=security,
        periods=periods,
        as_of=now_utc.date(),
        config=config,
    )

    # Peer percentile calculations
    industry = security.industry or security.sector or "General"
    peer_percentiles: dict[str, float | None] = {}

    for m in metrics:
        if m.value is None:
            peer_percentiles[m.metric_key] = None
            continue

        # Find peers in same industry
        peer_stmt = (
            select(FundamentalMetric.value)
            .join(Security, Security.id == FundamentalMetric.security_id)
            .where(
                FundamentalMetric.metric_key == m.metric_key,
                FundamentalMetric.peer_group == m.peer_group,
                FundamentalMetric.value.is_not(None),
            )
        )
        peer_vals = [float(v) for v in session.scalars(peer_stmt).all() if v is not None]
        if len(peer_vals) >= config.min_peer_group_size:
            less_count = sum(1 for v in peer_vals if v < m.value)
            eq_count = sum(1 for v in peer_vals if v == m.value)
            pct = ((less_count + 0.5 * eq_count) / len(peer_vals)) * 100.0
            peer_percentiles[m.metric_key] = round(pct, 1)
        else:
            peer_percentiles[m.metric_key] = None

    latest_period = periods[-1] if periods else None
    data_age_days = (now_utc.date() - latest_period.period_end).days if latest_period else None

    # Check if estimated publication date
    has_estimated_dates = any(p.published_at_method == "estimated" for p in periods)

    limitations = [
        "Fundamental metrics are computed point-in-time using only disclosures "
        "published as of effective date.",
        "Flow metrics (Revenue, Operating Profit, PAT, CFO) represent Trailing "
        "Twelve Months (TTM) over 4 published quarters.",
    ]
    if has_estimated_dates:
        limitations.append(
            "Source: Yahoo Finance, unofficial, last ~4 to 5 quarters, publication "
            "dates estimated (period_end + 45/60 days)."
        )

    periods_out = [
        {
            "id": str(p.id),
            "period_end": p.period_end.isoformat(),
            "period_type": p.period_type,
            "basis": p.basis,
            "published_at": p.published_at.isoformat(),
            "published_at_method": p.published_at_method,
            "version": p.version,
            "revenue": p.revenue,
            "operating_profit": p.operating_profit,
            "pat": p.pat,
            "interest_expense": p.interest_expense,
            "total_debt": p.total_debt,
            "total_equity": p.total_equity,
            "total_assets": p.total_assets,
            "cash_from_operations": p.cash_from_operations,
            "extra": p.extra,
        }
        for p in reversed(periods)  # Most recent first
    ]

    metrics_out = [
        {
            "metric_key": m.metric_key,
            "value": m.value,
            "peer_percentile": peer_percentiles.get(m.metric_key),
            "peer_group": m.peer_group,
            "status": m.status,
            "details": m.details,
            "data_age_days": m.data_age_days,
        }
        for m in metrics
    ]

    return {
        "symbol": norm_symbol,
        "company_name": security.company_name,
        "industry": industry,
        "sector": security.sector,
        "as_of": now_utc.date().isoformat(),
        "data_age_days": data_age_days,
        "periods": periods_out,
        "metrics": metrics_out,
        "limitations": limitations,
        "source_note": (
            "Source: Yahoo Finance, unofficial, last ~4 to 5 quarters, publication dates estimated"
            if has_estimated_dates
            else "Official exchange financial results"
        ),
    }
