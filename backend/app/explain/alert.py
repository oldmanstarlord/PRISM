"""Evidence-bound alert explanation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models import Alert
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
class AlertSubject:
    alert_id: UUID

    @property
    def key(self) -> str:
        return f"alert:{self.alert_id}"


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


class AlertExplainer:
    subject_type = "alert"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, AlertSubject):
            raise TypeError("alert explainer requires AlertSubject")

        alert = session.get(Alert, subject.alert_id)
        if alert is None:
            raise LookupError(f"alert not found: {subject.alert_id}")

        created_date = alert.created_at.date() if alert.created_at else date.today()
        effective_date = as_of or created_date
        age_days = (date.today() - effective_date).days

        inputs = dict(alert.inputs_ref) if alert.inputs_ref else {}
        observed_val = inputs.get("current", alert.score)
        prior_val = inputs.get("previous", None)
        thresh_val = inputs.get("threshold", "configured")

        obs_formatted = (
            round(float(observed_val), 2)
            if isinstance(observed_val, (int, float))
            else str(observed_val)
        )
        prior_formatted = (
            round(float(prior_val), 2)
            if isinstance(prior_val, (int, float))
            else str(prior_val)
            if prior_val is not None
            else None
        )

        evidence: list[Evidence] = [
            _evidence(
                evidence_id="alert:rule",
                kind="rule",
                label="Alert Rule Type",
                value=alert.alert_type.replace("_", " ").title(),
                unit=None,
                window=None,
                source_table="alert",
                source_ref=str(alert.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="alert:reason",
                kind="rule",
                label="Trigger Reason",
                value=alert.reason,
                unit=None,
                window=None,
                source_table="alert",
                source_ref=str(alert.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="alert:observed",
                kind="statistic",
                label="Observed Value",
                value=obs_formatted,
                unit=None,
                window=None,
                source_table="alert",
                source_ref=str(alert.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="alert:threshold",
                kind="config",
                label="Configured Threshold",
                value=str(thresh_val),
                unit=None,
                window=None,
                source_table="model_config",
                source_ref=alert.config_version,
                as_of=effective_date,
                data_age_days=age_days,
            ),
            _evidence(
                evidence_id="alert:status",
                kind="rule",
                label="Alert Status",
                value=alert.status,
                unit=None,
                window=None,
                source_table="alert",
                source_ref=str(alert.id),
                as_of=effective_date,
                data_age_days=age_days,
            ),
        ]
        if prior_formatted is not None:
            evidence.append(
                _evidence(
                    evidence_id="alert:prior",
                    kind="statistic",
                    label="Prior Baseline Value",
                    value=prior_formatted,
                    unit=None,
                    window=None,
                    source_table="alert",
                    source_ref=str(alert.id),
                    as_of=effective_date,
                    data_age_days=age_days,
                )
            )
        return evidence

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        if not isinstance(subject, AlertSubject):
            raise TypeError("alert explainer requires AlertSubject")

        ev_map = {item.evidence_id: item for item in evidence}
        effective_date = evidence[0].as_of
        data_age = evidence[0].data_age_days

        rule_val = ev_map["alert:rule"].value
        reason_val = ev_map["alert:reason"].value
        obs_val = ev_map["alert:observed"].value
        thresh_val = ev_map["alert:threshold"].value
        status_val = ev_map["alert:status"].value

        headline = f"Alert Explanation: {rule_val}"

        summary_sentences = [
            ExplanationSentence(
                text=f"Alert triggered by condition: {reason_val}",
                evidence_ids=["alert:reason"],
            ),
            ExplanationSentence(
                text=(
                    f"The observed metric was {obs_val} against a configured "
                    f"threshold of {thresh_val}."
                ),
                evidence_ids=["alert:observed", "alert:threshold"],
            ),
        ]

        detail_sentences = [
            ExplanationSentence(
                text=f"Current alert status is '{status_val}'.",
                evidence_ids=["alert:status"],
            ),
            ExplanationSentence(
                text=f"Trigger rule category: {rule_val}.",
                evidence_ids=["alert:rule"],
            ),
        ]

        sections = [
            ExplanationSection(
                key="alert_context",
                title="Trigger Condition & Evaluation Inputs",
                sentences=detail_sentences,
            )
        ]

        limitations = [
            "Alerts indicate descriptive threshold crossings, not trading advice.",
            "Alert conditions are evaluated on daily closing prices and event records.",
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
                            "Alert conditions are evaluated from stored audit logs "
                            "and point-in-time calculation runs."
                        ),
                        evidence_ids=["alert:observed"],
                    )
                ],
            ),
            data_age=ExplanationDataAge(
                days=data_age,
                as_of=effective_date,
                status="current" if (data_age or 0) <= 5 else "stale",
            ),
            template_version=template_version,
            subject=ExplanationSubject(type="alert", key=subject.key),
            disclaimer=config.get(
                "disclaimer",
                "PRISM provides descriptive risk explanations, not investment advice.",
            ),
            effective_time=effective_date,
            method="explainable_alerts",
            method_version="alerts_v1",
            computed_at=datetime.now(UTC),
        )


registry.register(AlertExplainer())
