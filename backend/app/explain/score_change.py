"""Evidence-bound risk score change explainer using Step 12 change evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    ScoreComponentDefinition,
    ScoreComponentValue,
    ScoreRun,
    Security,
    SecurityAlias,
    StockRiskResult,
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


@dataclass(frozen=True)
class ScoreChangeSubject:
    symbol: str
    as_of: date | None = None

    @property
    def key(self) -> str:
        date_str = self.as_of.isoformat() if self.as_of else "latest"
        return f"{self.symbol.upper()}:{date_str}"


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


class ScoreChangeExplainer:
    subject_type = "score_change"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, ScoreChangeSubject):
            raise TypeError("score change explainer requires ScoreChangeSubject")

        symbol = subject.symbol.upper()
        alias = session.scalars(
            select(SecurityAlias)
            .where(func.upper(SecurityAlias.symbol) == symbol)
            .order_by(desc(SecurityAlias.valid_from))
        ).first()
        if alias is None:
            raise LookupError(f"unknown symbol: {symbol}")

        security = session.get(Security, alias.security_id)
        if security is None:
            raise LookupError(f"security record missing for {symbol}")

        run_query = (
            select(ScoreRun)
            .join(StockRiskResult, StockRiskResult.run_id == ScoreRun.id)
            .where(
                StockRiskResult.security_id == security.id,
                ScoreRun.status == "completed",
            )
        )
        if subject.as_of is not None:
            run_query = run_query.where(ScoreRun.as_of_date <= subject.as_of)
        runs = session.scalars(run_query.order_by(desc(ScoreRun.as_of_date)).limit(2)).all()

        if not runs:
            raise LookupError(f"no score runs found for symbol {symbol}")

        latest_run = runs[0]
        effective_date = latest_run.as_of_date
        age_days = (date.today() - effective_date).days

        latest_result = session.scalar(
            select(StockRiskResult).where(
                StockRiskResult.run_id == latest_run.id,
                StockRiskResult.security_id == security.id,
            )
        )
        if latest_result is None:
            raise LookupError(f"missing score result for {symbol}")

        has_prior = len(runs) >= 2
        prior_run = runs[1] if has_prior else None
        prior_result = (
            session.scalar(
                select(StockRiskResult).where(
                    StockRiskResult.run_id == prior_run.id,
                    StockRiskResult.security_id == security.id,
                )
            )
            if prior_run
            else None
        )

        curr_score = float(latest_result.total_score)
        prev_score = float(prior_result.total_score) if prior_result else curr_score
        score_delta = round(curr_score - prev_score, 2)

        definitions = {
            d.component_id: d for d in session.scalars(select(ScoreComponentDefinition)).all()
        }

        latest_vals = {
            v.component_id: v
            for v in session.scalars(
                select(ScoreComponentValue).where(
                    ScoreComponentValue.run_id == latest_run.id,
                    ScoreComponentValue.security_id == security.id,
                )
            ).all()
        }
        prior_vals = (
            {
                v.component_id: v
                for v in session.scalars(
                    select(ScoreComponentValue).where(
                        ScoreComponentValue.run_id == prior_run.id,
                        ScoreComponentValue.security_id == security.id,
                    )
                ).all()
            }
            if prior_run
            else {}
        )

        component_shifts: list[dict[str, Any]] = []
        for cid, curr_v in latest_vals.items():
            if curr_v.points is None:
                continue
            prev_v = prior_vals.get(cid)
            prev_pts = (
                float(prev_v.points)
                if (prev_v and prev_v.points is not None)
                else float(curr_v.points)
            )
            prev_pct = (
                float(prev_v.percentile_rank)
                if (prev_v and prev_v.percentile_rank is not None)
                else float(curr_v.percentile_rank or 0)
            )
            curr_pts = float(curr_v.points)
            curr_pct = float(curr_v.percentile_rank or 0)

            pt_diff = curr_pts - prev_pts
            pct_diff = curr_pct - prev_pct
            cdef = definitions.get(cid)
            cname = cdef.name if cdef else cid

            component_shifts.append(
                {
                    "component_id": cid,
                    "name": cname,
                    "point_change": round(pt_diff, 2),
                    "percentile_change": round(pct_diff, 2),
                    "current_points": round(curr_pts, 2),
                }
            )

        component_shifts.sort(key=lambda item: abs(float(item["point_change"])), reverse=True)
        top1 = (
            component_shifts[0]
            if component_shifts
            else {"name": "None", "point_change": 0.0, "percentile_change": 0.0}
        )
        top2 = (
            component_shifts[1]
            if len(component_shifts) > 1
            else {"name": "None", "point_change": 0.0, "percentile_change": 0.0}
        )
        top3 = (
            component_shifts[2]
            if len(component_shifts) > 2
            else {"name": "None", "point_change": 0.0, "percentile_change": 0.0}
        )

        eval_dates = (
            f"{prior_run.as_of_date.isoformat()} to {latest_run.as_of_date.isoformat()}"
            if prior_run
            else "initial baseline run"
        )

        evidence: list[Evidence] = [
            _evidence(
                evidence_id="change:score_delta",
                kind="statistic",
                label="Total Risk Score Change",
                value=score_delta,
                unit="points",
                window=None,
                source_table="stock_risk_result",
                source_ref=str(latest_result.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="change:current_score",
                kind="statistic",
                label="Current Risk Score",
                value=round(curr_score, 2),
                unit="points",
                window=None,
                source_table="stock_risk_result",
                source_ref=str(latest_result.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="change:previous_score",
                kind="statistic",
                label="Previous Risk Score",
                value=round(prev_score, 2),
                unit="points",
                window=None,
                source_table="stock_risk_result" if prior_result else "baseline",
                source_ref=str(prior_result.id if prior_result else latest_result.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="change:dates",
                kind="rule",
                label="Evaluation Period Dates",
                value=eval_dates,
                unit=None,
                window=None,
                source_table="score_run",
                source_ref=str(latest_run.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="change:top1_driver",
                kind="statistic",
                label=f"Primary Driver ({top1['name']})",
                value=(
                    f"{top1['name']}: {top1['point_change']:+.2f} pts "
                    f"(pct rank {top1['percentile_change']:+.1f})"
                ),
                unit="points",
                window=None,
                source_table="score_component_value",
                source_ref=str(top1.get("component_id", "primary")),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="change:top2_driver",
                kind="statistic",
                label=f"Secondary Driver ({top2['name']})",
                value=f"{top2['name']}: {top2['point_change']:+.2f} pts",
                unit="points",
                window=None,
                source_table="score_component_value",
                source_ref=str(top2.get("component_id", "secondary")),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="change:top3_driver",
                kind="statistic",
                label=f"Tertiary Driver ({top3['name']})",
                value=f"{top3['name']}: {top3['point_change']:+.2f} pts",
                unit="points",
                window=None,
                source_table="score_component_value",
                source_ref=str(top3.get("component_id", "tertiary")),
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
        if not isinstance(subject, ScoreChangeSubject):
            raise TypeError("score change explainer requires ScoreChangeSubject")

        ev_map = {item.evidence_id: item for item in evidence}
        effective_date = evidence[0].as_of
        data_age = evidence[0].data_age_days

        symbol = subject.symbol.upper()
        score_delta = float(ev_map["change:score_delta"].value or 0)
        curr_score = ev_map["change:current_score"].value
        prev_score = ev_map["change:previous_score"].value
        dates_val = ev_map["change:dates"].value
        top1_desc = str(ev_map["change:top1_driver"].value)
        top2_desc = str(ev_map["change:top2_driver"].value)
        top3_desc = str(ev_map["change:top3_driver"].value)

        delta_dir = (
            "rose" if score_delta > 0 else "fell" if score_delta < 0 else "remained unchanged"
        )
        headline = f"Risk Score Trajectory for {symbol} ({score_delta:+.1f} Points)"

        summary_sentences = [
            ExplanationSentence(
                text=(
                    f"Total risk score {delta_dir} by {abs(score_delta):.1f} points "
                    f"(from {prev_score} to {curr_score}) across {dates_val}."
                ),
                evidence_ids=[
                    "change:score_delta",
                    "change:current_score",
                    "change:previous_score",
                    "change:dates",
                ],
            ),
            ExplanationSentence(
                text=f"Primary risk driver shift: {top1_desc}.",
                evidence_ids=["change:top1_driver"],
            ),
        ]

        component_sentences = [
            ExplanationSentence(
                text=f"Secondary component shift: {top2_desc}.",
                evidence_ids=["change:top2_driver"],
            ),
            ExplanationSentence(
                text=f"Tertiary component shift: {top3_desc}.",
                evidence_ids=["change:top3_driver"],
            ),
            ExplanationSentence(
                text=(
                    "Component shifts reflect changes in percentile rank across "
                    "peer cross-sections between run dates."
                ),
                evidence_ids=["change:score_delta"],
            ),
        ]

        sections = [
            ExplanationSection(
                key="component_shifts",
                title="Top Component Risk Shifts",
                sentences=component_sentences,
            ),
        ]

        limitations = [
            "Score trajectory reflects historical inputs, not a forward price prediction.",
            "Shifts stem from metric movements and peer cross-sectional threshold changes.",
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
                            "Score trajectory is computed from deterministic point-in-time "
                            "score runs and component values."
                        ),
                        evidence_ids=["change:score_delta", "change:current_score"],
                    )
                ],
            ),
            data_age=ExplanationDataAge(
                days=data_age,
                as_of=effective_date,
                status="current" if (data_age or 0) <= 5 else "stale",
            ),
            template_version=template_version,
            subject=ExplanationSubject(type="score_change", key=subject.key),
            disclaimer=config.get(
                "disclaimer",
                "PRISM provides descriptive risk explanations, not investment advice.",
            ),
            effective_time=effective_date,
            method="risk_score_trajectory",
            method_version="score_change_v1",
            computed_at=datetime.now(UTC),
        )


registry.register(ScoreChangeExplainer())
