"""Fundamental risk score components (dimension: fundamentals).

Components:
- fund_leverage: Financial Leverage (Debt/Equity or Assets/Equity for financials)
- fund_coverage: Solvency / Interest Coverage (EBIT / Interest)
- fund_profit_trend: TTM YoY Profit Growth Trend
- fund_cashflow_quality: Cash Flow Quality (CFO / PAT)
"""

from __future__ import annotations

from datetime import date
from typing import cast
from uuid import UUID

from sqlalchemy import select

from backend.app.core.model_config import FundamentalAnalysisConfig
from backend.app.db.models import Security
from backend.app.fundamentals.metrics import (
    CalculatedMetric,
    compute_ttm_metrics,
    get_usable_periods,
)
from backend.app.risk_score.components.base import ComponentValue, RiskContext


def _get_fundamental_metrics_cache(
    context: RiskContext,
    universe: list[tuple[UUID, str, str]],
) -> dict[UUID, dict[str, CalculatedMetric]]:
    """Retrieve and cache all point-in-time fundamental metrics for universe securities."""
    cache_key = "fundamental_metrics_map"
    if cache_key in context.cache:
        return cast(dict[UUID, dict[str, CalculatedMetric]], context.cache[cache_key])

    config_dict = context.config.get("fundamental_analysis", {})
    fund_config = (
        FundamentalAnalysisConfig(**config_dict) if config_dict else FundamentalAnalysisConfig()
    )

    sec_ids = [s[0] for s in universe]
    stmt = select(Security).where(Security.id.in_(sec_ids))
    securities = {s.id: s for s in context.session.scalars(stmt).all()}

    metrics_map: dict[UUID, dict[str, CalculatedMetric]] = {}
    for sec_id, _, _ in universe:
        sec = securities.get(sec_id)
        if sec is None:
            metrics_map[sec_id] = {}
            continue

        periods = get_usable_periods(
            context.session,
            sec_id,
            as_of=context.data_cutoff,
            basis_preference=fund_config.default_basis_preference,
        )
        calculated = compute_ttm_metrics(
            security=sec,
            periods=periods,
            as_of=context.as_of,
            config=fund_config,
        )
        metrics_map[sec_id] = {m.metric_key: m for m in calculated}

    context.cache[cache_key] = metrics_map
    return metrics_map


class FundLeverageComponent:
    """Financial Leverage component (higher is riskier).

    For non-financials: Debt to Equity.
    For financials/banks: Assets to Equity.
    """

    key = "fund_leverage"
    dimension = "fundamentals"
    direction = "higher_is_riskier"
    required_inputs = ["fundamental_period"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        f_map = _get_fundamental_metrics_cache(context, universe)
        results: list[ComponentValue] = []

        for sec_id, symbol, _industry in universe:
            metrics = f_map.get(sec_id, {})
            # Try debt_to_equity, fallback to asset_to_equity for financials
            m = metrics.get("debt_to_equity") or metrics.get("asset_to_equity")
            if m is None or m.value is None or m.status == "missing":
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=m.source_period_end if m else None,
                        data_age_days=m.data_age_days if m else None,
                        evidence_ref=m.details if m else {"reason": "no_published_results"},
                    )
                )
                continue

            status = m.status if m.status in ("flagged", "insufficient") else "ok"
            if m.data_age_days and m.data_age_days > 120:
                status = "stale"

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=m.value,
                    status=status,
                    data_as_of=m.source_period_end,
                    data_age_days=m.data_age_days,
                    evidence_ref={
                        "metric_key": m.metric_key,
                        "peer_group": m.peer_group,
                        "raw_details": m.details,
                    },
                )
            )

        return results


class FundCoverageComponent:
    """Solvency / Interest Coverage component (lower is riskier).

    EBIT to Interest Expense for non-financials.
    Marked missing for banks where interest is raw cost of funds.
    """

    key = "fund_coverage"
    dimension = "fundamentals"
    direction = "lower_is_riskier"
    required_inputs = ["fundamental_period"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        f_map = _get_fundamental_metrics_cache(context, universe)
        results: list[ComponentValue] = []

        for sec_id, symbol, _industry in universe:
            metrics = f_map.get(sec_id, {})
            m = metrics.get("interest_coverage")
            if m is None or m.value is None or m.status == "missing":
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=m.source_period_end if m else None,
                        data_age_days=m.data_age_days if m else None,
                        evidence_ref=m.details if m else {"reason": "not_applicable_or_missing"},
                    )
                )
                continue

            status = m.status if m.status in ("flagged", "insufficient") else "ok"
            if m.data_age_days and m.data_age_days > 120:
                status = "stale"

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=m.value,
                    status=status,
                    data_as_of=m.source_period_end,
                    data_age_days=m.data_age_days,
                    evidence_ref={
                        "metric_key": m.metric_key,
                        "peer_group": m.peer_group,
                        "raw_details": m.details,
                    },
                )
            )

        return results


class FundProfitTrendComponent:
    """TTM YoY Net Profit Growth Trend component (lower is riskier).

    Requires at least 5 quarters; otherwise status="insufficient".
    """

    key = "fund_profit_trend"
    dimension = "fundamentals"
    direction = "lower_is_riskier"
    required_inputs = ["fundamental_period"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        f_map = _get_fundamental_metrics_cache(context, universe)
        results: list[ComponentValue] = []

        for sec_id, symbol, _industry in universe:
            metrics = f_map.get(sec_id, {})
            m = metrics.get("ttm_profit_growth") or metrics.get("profit_growth")
            if m is None or m.status in ("missing", "insufficient") or m.value is None:
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status=m.status if m else "missing",
                        data_as_of=m.source_period_end if m else None,
                        data_age_days=m.data_age_days if m else None,
                        evidence_ref=m.details
                        if m
                        else {"reason": "insufficient_or_missing_quarters"},
                    )
                )
                continue

            status = "ok"
            if m.data_age_days and m.data_age_days > 120:
                status = "stale"

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=m.value,
                    status=status,
                    data_as_of=m.source_period_end,
                    data_age_days=m.data_age_days,
                    evidence_ref={
                        "metric_key": m.metric_key,
                        "peer_group": m.peer_group,
                        "raw_details": m.details,
                    },
                )
            )

        return results


class FundCashflowQualityComponent:
    """Cash Flow Quality component: CFO / PAT (lower is riskier).

    High CFO relative to reported PAT indicates conservative accounting and earnings quality.
    """

    key = "fund_cashflow_quality"
    dimension = "fundamentals"
    direction = "lower_is_riskier"
    required_inputs = ["fundamental_period"]

    def compute(
        self,
        as_of: date,
        universe: list[tuple[UUID, str, str]],
        context: RiskContext,
    ) -> list[ComponentValue]:
        f_map = _get_fundamental_metrics_cache(context, universe)
        results: list[ComponentValue] = []

        for sec_id, symbol, _industry in universe:
            metrics = f_map.get(sec_id, {})
            m = metrics.get("cash_flow_quality")
            if m is None or m.value is None or m.status == "missing":
                results.append(
                    ComponentValue(
                        security_id=sec_id,
                        symbol=symbol,
                        component_id=self.key,
                        raw_value=None,
                        status="missing",
                        data_as_of=m.source_period_end if m else None,
                        data_age_days=m.data_age_days if m else None,
                        evidence_ref=m.details
                        if m
                        else {"reason": "not_applicable_or_missing_cfo"},
                    )
                )
                continue

            status = "ok"
            if m.data_age_days and m.data_age_days > 120:
                status = "stale"

            results.append(
                ComponentValue(
                    security_id=sec_id,
                    symbol=symbol,
                    component_id=self.key,
                    raw_value=m.value,
                    status=status,
                    data_as_of=m.source_period_end,
                    data_age_days=m.data_age_days,
                    evidence_ref={
                        "metric_key": m.metric_key,
                        "peer_group": m.peer_group,
                        "raw_details": m.details,
                    },
                )
            )

        return results
