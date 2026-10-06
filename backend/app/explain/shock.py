"""Evidence-bound shock propagation explainer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID

import numpy as np
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    MstEdge,
    PortfolioHolding,
    PriceDailyAdjusted,
    Security,
    SecurityAlias,
    ShockResult,
    ShockScenario,
)
from backend.app.explain.evidence import Evidence
from backend.app.explain.registry import registry
from backend.app.explain.schemas import (
    ExplanationConfidence,
    ExplanationDataAge,
    ExplanationPayload,
    ExplanationSection,
    ExplanationSentence,
    ExplanationSubject,
)
from backend.app.mst_diagnostics.service import get_latest_mst_run_for_variant
from backend.app.portfolio.covariance import get_adjusted_returns_panel
from backend.app.portfolio.shock import calculate_mst_path_decay


@dataclass(frozen=True)
class ShockSubject:
    holding_symbol: str
    shocked_symbol: str
    portfolio_id: UUID | None = None
    scenario_id: UUID | None = None
    shock_pct: float = -10.0
    method: str = "regression_beta"

    @property
    def key(self) -> str:
        port_str = str(self.portfolio_id) if self.portfolio_id else "global"
        return (
            f"{port_str}:{self.shocked_symbol.upper()}->"
            f"{self.holding_symbol.upper()}:{self.shock_pct:.2f}:{self.method}"
        )


def _evidence(
    *,
    evidence_id: str,
    kind: Literal["statistic", "rule", "event", "config"],
    label: str,
    value: str | int | float | bool | None,
    unit: str | None,
    window: str | None,
    source_table: str,
    source_ref: str,
    as_of: date,
    data_age_days: int | None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        kind=kind,
        label=label,
        value=value,
        unit=unit,
        window=window,
        source_table=source_table,
        source_ref=source_ref,
        as_of=as_of,
        data_age_days=data_age_days,
    )


class ShockExplainer:
    subject_type = "shock"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, ShockSubject):
            raise TypeError("shock explainer requires ShockSubject")

        holding_sym = subject.holding_symbol.upper()
        shocked_sym = subject.shocked_symbol.upper()

        holding_sec = session.scalars(
            select(Security)
            .join(SecurityAlias, SecurityAlias.security_id == Security.id)
            .where(func.upper(SecurityAlias.symbol) == holding_sym)
        ).first()

        shocked_sec = session.scalars(
            select(Security)
            .join(SecurityAlias, SecurityAlias.security_id == Security.id)
            .where(func.upper(SecurityAlias.symbol) == shocked_sym)
        ).first()

        if holding_sec is None or shocked_sec is None:
            raise LookupError(f"could not resolve securities for {holding_sym} and {shocked_sym}")

        latest_price_date = session.scalar(
            select(func.max(PriceDailyAdjusted.trade_date)).where(
                PriceDailyAdjusted.security_id.in_([holding_sec.id, shocked_sec.id])
            )
        )
        effective_date = as_of or latest_price_date or date.today()

        scenario_row: ShockScenario | None = None
        result_row: ShockResult | None = None
        holding_weight = 0.0
        if subject.scenario_id is not None:
            scenario_row = session.get(ShockScenario, subject.scenario_id)
            if scenario_row is not None:
                result_row = session.scalar(
                    select(ShockResult).where(
                        ShockResult.scenario_id == scenario_row.id,
                        ShockResult.security_id == holding_sec.id,
                    )
                )
        elif subject.portfolio_id is not None:
            scenario_row = session.scalars(
                select(ShockScenario)
                .where(
                    ShockScenario.portfolio_id == subject.portfolio_id,
                    ShockScenario.shocked_security_id == shocked_sec.id,
                )
                .order_by(desc(ShockScenario.created_at))
            ).first()
            if scenario_row is not None:
                result_row = session.scalar(
                    select(ShockResult).where(
                        ShockResult.scenario_id == scenario_row.id,
                        ShockResult.security_id == holding_sec.id,
                    )
                )
            holding_record = session.scalar(
                select(PortfolioHolding).where(
                    PortfolioHolding.portfolio_id == subject.portfolio_id,
                    PortfolioHolding.security_id == holding_sec.id,
                )
            )
            if holding_record is not None:
                holding_weight = float(holding_record.weight)

        window_size = 252
        returns_df, _ = get_adjusted_returns_panel(
            session=session,
            security_ids=[holding_sec.id, shocked_sec.id],
            as_of=effective_date,
            window_size=window_size,
        )

        beta_val = 1.0 if holding_sym == shocked_sym else 0.0
        r_squared_val = 1.0 if holding_sym == shocked_sym else 0.0
        n_obs = len(returns_df) if not returns_df.empty else 0

        has_both = (
            not returns_df.empty
            and holding_sec.id in returns_df.columns
            and shocked_sec.id in returns_df.columns
        )
        if has_both:
            r_hold = returns_df[holding_sec.id].values
            r_shock = returns_df[shocked_sec.id].values
            var_shock = float(np.var(r_shock, ddof=1))
            if var_shock > 1e-12:
                cov_val = float(np.cov(r_hold, r_shock, ddof=1)[0, 1])
                beta_val = float(cov_val / var_shock)
                std_hold = float(np.std(r_hold, ddof=1))
                std_shock = float(np.sqrt(var_shock))
                if std_hold > 1e-12 and std_shock > 1e-12:
                    corr_val = float(cov_val / (std_hold * std_shock))
                    r_squared_val = float(np.clip(corr_val**2, 0.0, 1.0))

        if result_row is not None and result_row.method_detail:
            raw_sens = result_row.method_detail.get("sensitivity", beta_val)
            if isinstance(raw_sens, (int, float, str)):
                beta_val = float(raw_sens)
            holding_weight = float(result_row.weight)

        raw_shock_pct = scenario_row.shock_pct if scenario_row is not None else subject.shock_pct
        shock_pct = float(raw_shock_pct)
        estimated_impact = float(
            beta_val * shock_pct if holding_sym != shocked_sym else shock_pct
        )
        contribution_val = float(holding_weight * estimated_impact)

        path_desc = f"Direct pairwise regression transmission over {n_obs} daily returns"
        if subject.method == "mst_path_decay":
            latest_mst = get_latest_mst_run_for_variant(session, variant="raw")
            if latest_mst is not None:
                edges = session.execute(
                    select(MstEdge.symbol_a, MstEdge.symbol_b, MstEdge.correlation).where(
                        MstEdge.mst_run_id == latest_mst.id
                    )
                ).all()
                edge_list = [
                    (
                        r.symbol_a or "",
                        r.symbol_b or "",
                        float(r.correlation) if r.correlation is not None else 0.0,
                    )
                    for r in edges
                ]
                decay_map = calculate_mst_path_decay(edge_list, shocked_sym, [holding_sym])
                beta_val = float(decay_map.get(holding_sym, beta_val))
                path_desc = f"Attenuated tree path in MST run {latest_mst.id}"

        age_days = (date.today() - effective_date).days if effective_date else 0

        evidence: list[Evidence] = [
            _evidence(
                evidence_id="shock:impact",
                kind="statistic",
                label="Estimated Scenario Impact",
                value=round(estimated_impact, 2),
                unit="percentage",
                window=f"{window_size}d",
                source_table="shock_result" if result_row else "price_daily_adjusted",
                source_ref=str(result_row.id if result_row else holding_sec.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:sensitivity",
                kind="statistic",
                label="Sensitivity (Beta/Decay)",
                value=round(beta_val, 4),
                unit="ratio",
                window=f"{window_size}d",
                source_table="shock_result" if result_row else "price_daily_adjusted",
                source_ref=str(result_row.id if result_row else holding_sec.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:r_squared",
                kind="statistic",
                label="R-Squared Co-Movement",
                value=round(r_squared_val * 100, 2),
                unit="percentage",
                window=f"{window_size}d",
                source_table="price_daily_adjusted",
                source_ref=f"{holding_sec.id}:{shocked_sec.id}",
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:weight",
                kind="statistic",
                label="Holding Capital Weight",
                value=round(holding_weight * 100, 2),
                unit="percentage",
                window=None,
                source_table="portfolio_holding" if subject.portfolio_id else "model_input",
                source_ref=str(subject.portfolio_id or holding_sec.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:contribution",
                kind="statistic",
                label="Portfolio Loss Contribution",
                value=round(contribution_val, 2),
                unit="percentage",
                window=None,
                source_table="shock_result" if result_row else "model_derivation",
                source_ref=str(result_row.id if result_row else holding_sec.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:path",
                kind="rule",
                label="Transmission Path",
                value=path_desc,
                unit=None,
                window=None,
                source_table="shock_scenario" if scenario_row else "model_config",
                source_ref=subject.method,
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:assumption:linear",
                kind="config",
                label="Assumption: Linear Co-Movement",
                value=(
                    f"Asset sensitivity to {shocked_sym} estimated over "
                    f"trailing {window_size} days is assumed constant."
                ),
                unit=None,
                window=f"{window_size}d",
                source_table="model_config",
                source_ref="shock_simulator",
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:assumption:liquidity",
                kind="config",
                label="Assumption: No Liquidity Feedback",
                value="Prices adjust without order-book slippage or liquidation cascades.",
                unit=None,
                window=None,
                source_table="model_config",
                source_ref="shock_simulator",
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:assumption:stability",
                kind="config",
                label="Assumption: Covariance Stability",
                value="Historical dependence structure holds during hypothetical shock scenario.",
                unit=None,
                window=None,
                source_table="model_config",
                source_ref="shock_simulator",
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="shock:assumption:isolated",
                kind="config",
                label="Assumption: Isolated Exogenous Shock",
                value=(
                    f"Hypothetical stress is isolated to {shocked_sym} without "
                    "independent contemporaneous shocks."
                ),
                unit=None,
                window=None,
                source_table="model_config",
                source_ref="shock_simulator",
                as_of=effective_date,
                data_age_days=age_days,
            ),
        ]
        return evidence

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        if not isinstance(subject, ShockSubject):
            raise TypeError("shock explainer requires ShockSubject")

        ev_map = {item.evidence_id: item for item in evidence}
        effective_date = evidence[0].as_of
        data_age = evidence[0].data_age_days

        holding = subject.holding_symbol.upper()
        shocked = subject.shocked_symbol.upper()
        shock_pct = subject.shock_pct

        impact_val = ev_map["shock:impact"].value
        sens_val = ev_map["shock:sensitivity"].value
        r2_val = ev_map["shock:r_squared"].value
        weight_val = ev_map["shock:weight"].value
        contrib_val = ev_map["shock:contribution"].value
        path_desc = ev_map["shock:path"].value

        headline = (
            f"Scenario Shock Transmission for {holding} under "
            f"{shock_pct:.1f}% Shock to {shocked}"
        )

        summary_sentences = [
            ExplanationSentence(
                text=(
                    f"Holding {holding} has an estimated scenario impact of {impact_val}% "
                    f"under a {shock_pct:.1f}% shock to {shocked}."
                ),
                evidence_ids=["shock:impact"],
            ),
            ExplanationSentence(
                text=(
                    f"The sensitivity of {holding} to {shocked} is {sens_val} "
                    f"({subject.method}), indicating how it moves together with {shocked}."
                ),
                evidence_ids=["shock:sensitivity"],
            ),
            ExplanationSentence(
                text=(
                    f"The statistical co-movement accounts for an R-squared of {r2_val}% "
                    f"of {holding}'s return variation over the trailing window."
                ),
                evidence_ids=["shock:r_squared"],
            ),
        ]

        transmission_sentences = [
            ExplanationSentence(
                text=f"Transmission path: {path_desc}.",
                evidence_ids=["shock:path"],
            ),
            ExplanationSentence(
                text=(
                    f"Holding {holding} has a portfolio weight of {weight_val}%, "
                    f"contributing {contrib_val}% to estimated portfolio loss."
                ),
                evidence_ids=["shock:weight", "shock:contribution"],
            ),
        ]

        assumption_sentences = [
            ExplanationSentence(
                text=str(ev_map["shock:assumption:linear"].value),
                evidence_ids=["shock:assumption:linear"],
            ),
            ExplanationSentence(
                text=str(ev_map["shock:assumption:liquidity"].value),
                evidence_ids=["shock:assumption:liquidity"],
            ),
            ExplanationSentence(
                text=str(ev_map["shock:assumption:stability"].value),
                evidence_ids=["shock:assumption:stability"],
            ),
            ExplanationSentence(
                text=str(ev_map["shock:assumption:isolated"].value),
                evidence_ids=["shock:assumption:isolated"],
            ),
        ]

        confidence_level: Literal["high", "medium", "low"] = (
            "high" if float(r2_val or 0) > 10.0 else "medium"
        )
        confidence_reasons = [
            ExplanationSentence(
                text=(
                    "Sensitivity and R-squared are derived from empirical adjusted "
                    "daily returns without look-ahead."
                ),
                evidence_ids=["shock:sensitivity", "shock:r_squared"],
            ),
        ]

        sections = [
            ExplanationSection(
                key="transmission",
                title="Transmission Mechanism & Sensitivity",
                sentences=transmission_sentences,
            ),
            ExplanationSection(
                key="assumptions",
                title="Modeling Assumptions & Boundaries",
                sentences=assumption_sentences,
            ),
        ]

        limitations = [
            "Shock simulations are hypothetical stress scenarios, not forecasts.",
            "Historical co-movement does not guarantee stability during extreme liquidity crises.",
            "Order execution and market slippage are not modeled.",
        ]

        return ExplanationPayload(
            headline=headline,
            summary_points=summary_sentences,
            sections=sections,
            evidence=evidence,
            limitations=limitations,
            confidence=ExplanationConfidence(
                level=confidence_level,
                reasons=confidence_reasons,
            ),
            data_age=ExplanationDataAge(
                days=data_age,
                as_of=effective_date,
                status="current" if (data_age or 0) <= 5 else "stale",
            ),
            template_version=template_version,
            subject=ExplanationSubject(type="shock", key=subject.key),
            disclaimer=config.get(
                "disclaimer",
                "PRISM provides descriptive risk explanations, not investment advice.",
            ),
            effective_time=effective_date,
            method="shock_simulation",
            method_version=subject.method,
            computed_at=datetime.now(UTC),
        )


registry.register(ShockExplainer())
