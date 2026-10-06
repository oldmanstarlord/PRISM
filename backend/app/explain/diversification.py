"""Evidence-bound portfolio diversification and Effective Number of Bets explainer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    DiversificationRun,
    Portfolio,
    PortfolioHolding,
    PortfolioRiskContribution,
    PortfolioRiskRun,
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
from backend.app.portfolio.diversification import run_portfolio_diversification


@dataclass(frozen=True)
class DiversificationSubject:
    portfolio_id: UUID
    run_id: UUID | None = None

    @property
    def key(self) -> str:
        return f"portfolio:{self.portfolio_id}"


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


class DiversificationExplainer:
    subject_type = "diversification"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, DiversificationSubject):
            raise TypeError("diversification explainer requires DiversificationSubject")

        portfolio = session.get(Portfolio, subject.portfolio_id)
        if portfolio is None:
            raise LookupError(f"portfolio not found: {subject.portfolio_id}")

        div_run: DiversificationRun | None = None
        if subject.run_id is not None:
            div_run = session.get(DiversificationRun, subject.run_id)

        if div_run is None:
            div_run = session.scalar(
                select(DiversificationRun)
                .join(
                    PortfolioRiskRun,
                    PortfolioRiskRun.id == DiversificationRun.portfolio_risk_run_id,
                )
                .where(PortfolioRiskRun.portfolio_id == subject.portfolio_id)
                .order_by(desc(DiversificationRun.computed_at))
            )

        if div_run is None:
            risk_run = session.scalars(
                select(PortfolioRiskRun)
                .where(PortfolioRiskRun.portfolio_id == subject.portfolio_id)
                .order_by(desc(PortfolioRiskRun.as_of))
            ).first()
            if risk_run is not None:
                div_run = run_portfolio_diversification(session, risk_run.id)

        if div_run is None:
            raise LookupError("no completed diversification run is available for this portfolio")

        holdings = session.scalars(
            select(PortfolioHolding).where(PortfolioHolding.portfolio_id == subject.portfolio_id)
        ).all()
        holding_count = len(holdings)
        effective_date = as_of or (holdings[0].as_of if holdings else date.today())
        age_days = (date.today() - effective_date).days if effective_date else 0

        cluster_weights: dict[str, Any] = (
            dict(div_run.cluster_weights) if div_run.cluster_weights else {}
        )
        dominant_cluster = "None"
        dominant_cluster_weight = 0.0
        if cluster_weights:
            sorted_clusters = sorted(
                cluster_weights.items(), key=lambda item: float(str(item[1])), reverse=True
            )
            dominant_cluster = str(sorted_clusters[0][0])
            dominant_cluster_weight = float(str(sorted_clusters[0][1]))

        cluster_hhi = sum(float(str(w)) ** 2 for w in cluster_weights.values())

        prc_rows = session.scalars(
            select(PortfolioRiskContribution)
            .where(PortfolioRiskContribution.run_id == div_run.portfolio_risk_run_id)
            .order_by(desc(PortfolioRiskContribution.percent_contribution))
            .limit(3)
        ).all()
        top_prc_summary = ", ".join(
            f"{row.symbol} ({float(row.percent_contribution) * 100:.1f}%)"
            for row in prc_rows
        ) or "None recorded"

        evidence: list[Evidence] = [
            _evidence(
                evidence_id="div:enb_entropy",
                kind="statistic",
                label="Risk-Contribution Entropy ENB",
                value=round(float(div_run.enb_risk_entropy), 2),
                unit="bets",
                window=None,
                source_table="diversification_run",
                source_ref=str(div_run.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:enb_eigen",
                kind="statistic",
                label="Eigenvalue ENB",
                value=round(float(div_run.enb_eigen), 2),
                unit="bets",
                window=None,
                source_table="diversification_run",
                source_ref=str(div_run.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:holding_count",
                kind="statistic",
                label="Total Portfolio Holdings",
                value=holding_count,
                unit="count",
                window=None,
                source_table="portfolio_holding",
                source_ref=str(subject.portfolio_id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:dominant_cluster",
                kind="statistic",
                label="Dominant MST Cluster",
                value=dominant_cluster,
                unit=None,
                window=None,
                source_table="diversification_run",
                source_ref=str(div_run.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:dominant_weight",
                kind="statistic",
                label="Dominant Cluster Weight",
                value=round(dominant_cluster_weight * 100, 2),
                unit="percentage",
                window=None,
                source_table="diversification_run",
                source_ref=str(div_run.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:cluster_count",
                kind="statistic",
                label="Active Cluster Count",
                value=len(cluster_weights),
                unit="count",
                window=None,
                source_table="diversification_run",
                source_ref=str(div_run.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:cluster_hhi",
                kind="statistic",
                label="Cluster Concentration HHI",
                value=round(cluster_hhi, 4),
                unit="index",
                window=None,
                source_table="diversification_run",
                source_ref=str(div_run.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:top_risk_assets",
                kind="statistic",
                label="Top Risk Contributors",
                value=top_prc_summary,
                unit=None,
                window=None,
                source_table="portfolio_risk_contribution",
                source_ref=str(div_run.portfolio_risk_run_id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:formula_entropy",
                kind="rule",
                label="Entropy Calculation Formula",
                value="exp(-sum(p_i * ln(p_i))) with clamped percentage risk contributions p_i.",
                unit=None,
                window=None,
                source_table="model_config",
                source_ref="portfolio_diversification",
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="div:formula_eigen",
                kind="rule",
                label="Eigenvalue Calculation Formula",
                value=(
                    "(sum lambda_i)^2 / sum (lambda_i^2) across correlation eigenvalues that "
                    "describe how assets move together with each other."
                ),
                unit=None,
                window=None,
                source_table="model_config",
                source_ref="portfolio_diversification",
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
        if not isinstance(subject, DiversificationSubject):
            raise TypeError("diversification explainer requires DiversificationSubject")

        ev_map = {item.evidence_id: item for item in evidence}
        effective_date = evidence[0].as_of
        data_age = evidence[0].data_age_days

        enb_entropy = ev_map["div:enb_entropy"].value
        enb_eigen = ev_map["div:enb_eigen"].value
        holding_count = ev_map["div:holding_count"].value
        dominant_cluster = ev_map["div:dominant_cluster"].value
        dominant_weight = ev_map["div:dominant_weight"].value
        cluster_count = ev_map["div:cluster_count"].value
        cluster_hhi = ev_map["div:cluster_hhi"].value
        top_assets = ev_map["div:top_risk_assets"].value
        formula_entropy = ev_map["div:formula_entropy"].value
        formula_eigen = ev_map["div:formula_eigen"].value

        headline = f"Portfolio Diversification & Effective Number of Bets ({enb_entropy} Bets)"

        summary_sentences = [
            ExplanationSentence(
                text=(
                    f"The portfolio delivers {enb_entropy} effective bets based on "
                    f"risk-contribution entropy across {holding_count} holdings."
                ),
                evidence_ids=["div:enb_entropy", "div:holding_count"],
            ),
            ExplanationSentence(
                text=(
                    f"The primary risk cluster is {dominant_cluster}, accounting for "
                    f"{dominant_weight}% of portfolio capital."
                ),
                evidence_ids=["div:dominant_cluster", "div:dominant_weight"],
            ),
            ExplanationSentence(
                text=(
                    f"The eigenvalue-derived effective bets is {enb_eigen}, reflecting "
                    "independent statistical dimensions of co-movement."
                ),
                evidence_ids=["div:enb_eigen"],
            ),
        ]

        cluster_sentences = [
            ExplanationSentence(
                text=(
                    f"Holdings are mapped into {cluster_count} active MST clusters with an "
                    f"aggregate cluster HHI of {cluster_hhi}."
                ),
                evidence_ids=["div:cluster_count", "div:cluster_hhi"],
            ),
            ExplanationSentence(
                text=f"Top percentage risk contributors driving concentration are: {top_assets}.",
                evidence_ids=["div:top_risk_assets"],
            ),
        ]

        computation_sentences = [
            ExplanationSentence(
                text=f"Entropy ENB is computed as: {formula_entropy}",
                evidence_ids=["div:formula_entropy"],
            ),
            ExplanationSentence(
                text=f"Eigenvalue ENB is computed as: {formula_eigen}",
                evidence_ids=["div:formula_eigen"],
            ),
            ExplanationSentence(
                text=(
                    "When risk contributions are equally dispersed across N assets, entropy "
                    "ENB equals N; when one asset dominates, it approaches 1."
                ),
                evidence_ids=["div:formula_entropy"],
            ),
        ]

        sections = [
            ExplanationSection(
                key="cluster_concentration",
                title="Cluster Dominance & Concentration Findings",
                sentences=cluster_sentences,
            ),
            ExplanationSection(
                key="computation_method",
                title="How Effective Number of Bets is Computed",
                sentences=computation_sentences,
            ),
        ]

        limitations = [
            "Effective Number of Bets is a structural metric, not a return guarantee.",
            "Clusters represent statistical co-movement, not corporate linkages.",
            "Calculations rely on trailing covariance and end-of-day market data.",
        ]

        return ExplanationPayload(
            headline=headline,
            summary_points=summary_sentences,
            sections=sections,
            evidence=evidence,
            limitations=limitations,
            confidence=ExplanationConfidence(
                level="high",
                reasons=[
                    ExplanationSentence(
                        text=(
                            "Diversification and cluster weights are computed from verified "
                            "point-in-time covariance and MST structures."
                        ),
                        evidence_ids=["div:enb_entropy", "div:enb_eigen"],
                    )
                ],
            ),
            data_age=ExplanationDataAge(
                days=data_age,
                as_of=effective_date,
                status="current" if (data_age or 0) <= 5 else "stale",
            ),
            template_version=template_version,
            subject=ExplanationSubject(type="diversification", key=subject.key),
            disclaimer=config.get(
                "disclaimer",
                "PRISM provides descriptive risk explanations, not investment advice.",
            ),
            effective_time=effective_date,
            method="portfolio_diversification_enb",
            method_version="enb_v1",
            computed_at=datetime.now(UTC),
        )


registry.register(DiversificationExplainer())
