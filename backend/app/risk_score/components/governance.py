"""Governance risk score components (dimension: governance).

Components:
  - gov_promoter_pledge:        Pledge level + 2-quarter trend (higher is riskier)
  - gov_promoter_holding_change: Decline in promoter stake (mapped: decline → higher risk)
  - gov_institutional_flow:     Net FII+DII outflow (mapped: outflow → higher risk)
  - gov_insider_activity:       Net insider selling ratio (higher is riskier)

Each component reads from shareholding_pattern and insider_trade tables using
point-in-time (published_at <= data_cutoff) filtering.
Results carry evidence_ref with config thresholds and input values for transparency (D3).
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from uuid import UUID

from backend.app.db.models import SecurityMarketStat
from backend.app.governance.config import GovernanceAnalysisConfig
from backend.app.governance.metrics import (
    compute_insider_activity,
    compute_institutional_flow,
    compute_pledge_metrics,
)
from backend.app.governance.service import (
    get_insider_trades_as_of,
    get_shareholding_as_of,
)
from backend.app.risk_score.components.base import ComponentValue, RiskContext


def _load_gov_config(context: RiskContext) -> GovernanceAnalysisConfig:
    """Load governance config from context, falling back to defaults."""
    config_dict = context.config.get("governance_analysis", {})
    return GovernanceAnalysisConfig(**config_dict) if config_dict else GovernanceAnalysisConfig()


def _get_market_cap(context: RiskContext, security_id: UUID) -> float | None:
    """Fetch the most recent market cap (INR) for a security, point-in-time."""
    from sqlalchemy import select

    row = context.session.scalar(
        select(SecurityMarketStat)
        .where(
            SecurityMarketStat.security_id == security_id,
            SecurityMarketStat.trade_date <= context.as_of,
        )
        .order_by(SecurityMarketStat.trade_date.desc())
        .limit(1)
    )
    if row is None:
        return None
    market_cap = row.market_cap
    if market_cap is None:
        return None
    return float(market_cap)


def _get_shareholding_cache(
    context: RiskContext,
    security_id: UUID,
) -> list[dict[str, Any]]:
    """Cache shareholding patterns per security to avoid N+1 queries."""
    cache_key = f"shareholding_{security_id}"
    if cache_key not in context.cache:
        context.cache[cache_key] = get_shareholding_as_of(
            context.session, security_id, context.data_cutoff
        )
    return cast(list[dict[str, Any]], context.cache[cache_key])


def _get_trade_cache(
    context: RiskContext,
    security_id: UUID,
) -> list[dict[str, Any]]:
    """Cache insider trades per security to avoid N+1 queries."""
    cache_key = f"insider_trades_{security_id}"
    if cache_key not in context.cache:
        context.cache[cache_key] = get_insider_trades_as_of(
            context.session, security_id, context.data_cutoff
        )
    return cast(list[dict[str, Any]], context.cache[cache_key])


# ---------------------------------------------------------------------------
# Component 1: Promoter Pledge Risk
# ---------------------------------------------------------------------------


class GovPromoterPledgeComponent:
    """Pledged promoter shares % (level + 2Q change) — higher is riskier.

    Raw value is a composite score:
      raw_value = pledge_level + max(0, pledge_change) * 0.5

    This blends the absolute pledge level with a recent rising trend.
    The combined value is ranked in the universe percentile.
    """

    key = "gov_promoter_pledge"
    component_id = "gov_promoter_pledge"
    dimension = "governance"
    direction = "higher_is_riskier"
    scope = "universe"
    min_group_size = 5
    weight = 1.0
    required_inputs: list[str] = ["shareholding_pattern"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        cfg = _load_gov_config(context)
        results: list[ComponentValue] = []

        for security_id, symbol, _ in universe:
            patterns = _get_shareholding_cache(context, security_id)
            m = compute_pledge_metrics(patterns, cfg)

            if m.status == "missing":
                results.append(
                    ComponentValue(
                        security_id=security_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=None,
                        data_age_days=None,
                        evidence_ref={
                            "reason": "No shareholding pattern data available.",
                            "threshold_pledge_high": cfg.pledge_level_high_threshold,
                        },
                    )
                )
                continue

            # Composite: pledge level + rising trend bonus
            pledge_level = m.pledge_level or 0.0
            pledge_change = m.pledge_change or 0.0
            raw_value = pledge_level + max(0.0, pledge_change) * 0.5

            data_age_days = (as_of - m.quarter_end).days if m.quarter_end != date.min else None

            results.append(
                ComponentValue(
                    security_id=security_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(raw_value, 4),
                    status=m.status,
                    data_as_of=m.quarter_end if m.quarter_end != date.min else None,
                    data_age_days=data_age_days,
                    evidence_ref={
                        "pledge_level_pct": m.pledge_level,
                        "pledge_change_pct": m.pledge_change,
                        "n_quarters": m.n_quarters_available,
                        "threshold_high": cfg.pledge_level_high_threshold,
                        "threshold_change": cfg.pledge_change_high_threshold,
                        "formula": "pledge_level + max(0, pledge_change) * 0.5",
                    },
                )
            )

        return results


# ---------------------------------------------------------------------------
# Component 2: Promoter Holding Change
# ---------------------------------------------------------------------------


class GovPromoterHoldingChangeComponent:
    """Promoter stake % change over last N quarters — decline is riskier.

    Raw value = negative of change (so decline → higher raw_value → higher risk).
      raw_value = -promoter_change (so falling stake = higher raw score)
    """

    key = "gov_promoter_holding_change"
    component_id = "gov_promoter_holding_change"
    dimension = "governance"
    direction = "higher_is_riskier"
    scope = "universe"
    min_group_size = 5
    weight = 1.0
    required_inputs: list[str] = ["shareholding_pattern"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        cfg = _load_gov_config(context)
        results: list[ComponentValue] = []

        for security_id, symbol, _ in universe:
            patterns = _get_shareholding_cache(context, security_id)
            m = compute_pledge_metrics(patterns, cfg)

            if m.status == "missing" or m.promoter_change is None:
                results.append(
                    ComponentValue(
                        security_id=security_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing" if m.status == "missing" else "insufficient",
                        data_as_of=None,
                        data_age_days=None,
                        evidence_ref={
                            "reason": "Insufficient quarters or missing promoter data.",
                            "n_quarters": m.n_quarters_available,
                        },
                    )
                )
                continue

            # Invert: decline → positive raw → higher risk rank
            raw_value = -m.promoter_change
            data_age_days = (as_of - m.quarter_end).days if m.quarter_end != date.min else None

            results.append(
                ComponentValue(
                    security_id=security_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(raw_value, 4),
                    status="ok",
                    data_as_of=m.quarter_end if m.quarter_end != date.min else None,
                    data_age_days=data_age_days,
                    evidence_ref={
                        "promoter_pct_latest": m.promoter_pct,
                        "promoter_change_pct": m.promoter_change,
                        "raw_value": round(raw_value, 4),
                        "n_quarters": m.n_quarters_available,
                        "threshold_decline": cfg.promoter_decline_threshold,
                        "formula": "raw_value = -promoter_change (decline=higher risk)",
                    },
                )
            )

        return results


# ---------------------------------------------------------------------------
# Component 3: Institutional Flow (FII + DII)
# ---------------------------------------------------------------------------


class GovInstitutionalFlowComponent:
    """Net FII + DII holding change — outflow is riskier.

    Raw value = negative of combined_change (so outflow → positive raw → higher risk).
    """

    key = "gov_institutional_flow"
    component_id = "gov_institutional_flow"
    dimension = "governance"
    direction = "higher_is_riskier"
    scope = "universe"
    min_group_size = 5
    weight = 1.0
    required_inputs: list[str] = ["shareholding_pattern"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        cfg = _load_gov_config(context)
        results: list[ComponentValue] = []

        for security_id, symbol, _ in universe:
            patterns = _get_shareholding_cache(context, security_id)
            m = compute_institutional_flow(patterns, cfg)

            if m.status == "missing" or m.institutional_change is None:
                results.append(
                    ComponentValue(
                        security_id=security_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing" if m.status == "missing" else "insufficient",
                        data_as_of=None,
                        data_age_days=None,
                        evidence_ref={
                            "reason": "Insufficient quarters or missing FII/DII data.",
                            "n_quarters": m.n_quarters_available,
                        },
                    )
                )
                continue

            # Invert: outflow (negative change) → positive raw → higher risk
            raw_value = -m.institutional_change
            data_age_days = (as_of - m.quarter_end).days if m.quarter_end != date.min else None

            results.append(
                ComponentValue(
                    security_id=security_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(raw_value, 4),
                    status="ok",
                    data_as_of=m.quarter_end if m.quarter_end != date.min else None,
                    data_age_days=data_age_days,
                    evidence_ref={
                        "fii_pct": m.fii_pct,
                        "dii_pct": m.dii_pct,
                        "combined_pct": m.combined_pct,
                        "institutional_change_pct": m.institutional_change,
                        "n_quarters": m.n_quarters_available,
                        "threshold_outflow": cfg.institutional_outflow_threshold,
                        "formula": "raw_value = -(fii+dii change) (outflow=higher risk)",
                    },
                )
            )

        return results


# ---------------------------------------------------------------------------
# Component 4: Net Insider Selling Activity
# ---------------------------------------------------------------------------


class GovInsiderActivityComponent:
    """Net insider selling value / market_cap over rolling window — higher is riskier.

    If market cap is unavailable, uses net_sell_value directly (in crores) as raw.
    """

    key = "gov_insider_activity"
    component_id = "gov_insider_activity"
    dimension = "governance"
    direction = "higher_is_riskier"
    scope = "universe"
    min_group_size = 5
    weight = 1.0
    required_inputs: list[str] = ["insider_trade"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        cfg = _load_gov_config(context)
        results: list[ComponentValue] = []

        for security_id, symbol, _ in universe:
            trades = _get_trade_cache(context, security_id)
            market_cap = _get_market_cap(context, security_id)
            m = compute_insider_activity(trades, as_of, market_cap, cfg)

            if m.status == "missing":
                results.append(
                    ComponentValue(
                        security_id=security_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=None,
                        data_age_days=None,
                        evidence_ref={
                            "reason": "No insider trade disclosures in window.",
                            "window_days": cfg.insider_window_days,
                        },
                    )
                )
                continue

            # Use ratio when available, else fall back to net_sell_value in crores
            if m.insider_sell_ratio is not None:
                raw_value = m.insider_sell_ratio
            else:
                # Fallback: net sell value in INR crores (10^7)
                raw_value = m.net_sell_value / 1e7

            results.append(
                ComponentValue(
                    security_id=security_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=round(raw_value, 8),
                    status="ok",
                    data_as_of=m.window_end,
                    data_age_days=0,  # rolling window ending as_of
                    evidence_ref={
                        "window_days": m.window_days,
                        "trade_count": m.trade_count,
                        "buy_value_inr": m.buy_value,
                        "sell_value_inr": m.sell_value,
                        "net_sell_value_inr": m.net_sell_value,
                        "insider_sell_ratio": m.insider_sell_ratio,
                        "market_cap_inr": market_cap,
                        "threshold_elevated": cfg.insider_sell_ratio_elevated,
                        "formula": "net_sell_value / market_cap (if available)",
                    },
                )
            )

        return results
