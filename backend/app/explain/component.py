"""First shared explainer: one stored stock risk-component observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    ModelConfig,
    ScoreComponentDefinition,
    ScoreComponentValue,
    ScoreRun,
    Security,
    SecurityAlias,
    StockRiskResult,
)
from backend.app.explain.evidence import Evidence
from backend.app.explain.guardrails import evidence_bound_sentences
from backend.app.explain.registry import registry
from backend.app.explain.schemas import (
    ExplanationConfidence,
    ExplanationDataAge,
    ExplanationPayload,
    ExplanationSection,
    ExplanationSentence,
    ExplanationSubject,
)
from backend.app.explain.templates import build_sentence, direction_label


@dataclass(frozen=True)
class ComponentSubject:
    symbol: str
    component_key: str

    @property
    def key(self) -> str:
        return f"{self.symbol.upper()}:{self.component_key}"


def _number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


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


class RiskComponentExplainer:
    subject_type = "risk_component"

    def build_evidence(
        self, session: Session, subject: object, as_of: date | None
    ) -> list[Evidence]:
        if not isinstance(subject, ComponentSubject):
            raise TypeError("risk component explainer requires ComponentSubject")
        alias = session.scalars(
            select(SecurityAlias)
            .where(SecurityAlias.symbol == subject.symbol.upper())
            .order_by(desc(SecurityAlias.valid_from))
        ).first()
        if alias is None:
            raise LookupError(f"unknown symbol: {subject.symbol}")
        security = session.get(Security, alias.security_id)
        if security is None:
            raise LookupError(f"security missing for symbol: {subject.symbol}")

        run_query = (
            select(ScoreRun, StockRiskResult)
            .join(StockRiskResult, StockRiskResult.run_id == ScoreRun.id)
            .where(
                StockRiskResult.security_id == security.id,
                ScoreRun.status == "completed",
            )
        )
        if as_of is not None:
            run_query = run_query.where(ScoreRun.as_of_date <= as_of)
        run_pair = session.execute(
            run_query.order_by(desc(ScoreRun.as_of_date), desc(ScoreRun.completed_at)).limit(1)
        ).first()
        if run_pair is None:
            raise LookupError(f"no completed risk score for {subject.symbol}")
        run, _result = run_pair
        value = session.scalar(
            select(ScoreComponentValue).where(
                ScoreComponentValue.run_id == run.id,
                ScoreComponentValue.security_id == security.id,
                ScoreComponentValue.component_id == subject.component_key,
            )
        )
        definition = session.scalar(
            select(ScoreComponentDefinition).where(
                ScoreComponentDefinition.component_id == subject.component_key
            )
        )
        if value is None or definition is None:
            raise LookupError(
                f"component {subject.component_key!r} is unavailable for {subject.symbol}"
            )
        model_config = session.get(ModelConfig, run.model_config_id)
        configuration = dict(model_config.configuration) if model_config is not None else {}
        raw_weights = configuration.get("component_weights", {})
        weights = raw_weights if isinstance(raw_weights, dict) else {}
        weight = float(weights.get(subject.component_key, definition.weight))
        config_ref = str(model_config.id) if model_config is not None else str(definition.id)
        component_as_of = value.data_as_of or run.as_of_date

        prefix = f"score_component_value:{value.id}"
        evidence: list[Evidence] = [
            _evidence(
                evidence_id=f"score_component_definition:{definition.id}:name",
                kind="config",
                label="Component label",
                value=definition.name,
                unit=None,
                window=None,
                source_table="score_component_definition",
                source_ref=f"{definition.id}:name",
                as_of=run.as_of_date,
                data_age_days=None,
            ),
            _evidence(
                evidence_id=f"{prefix}:raw_value",
                kind="statistic",
                label="Raw value",
                value=_number(value.raw_value),
                unit=str(value.evidence_ref.get("unit"))
                if value.evidence_ref.get("unit") is not None
                else None,
                window=None,
                source_table="score_component_value",
                source_ref=f"{value.id}:raw_value",
                as_of=component_as_of,
                data_age_days=value.data_age_days,
            ),
            _evidence(
                evidence_id=f"{prefix}:percentile_rank",
                kind="statistic",
                label="Percentile rank",
                value=_number(value.percentile_rank),
                unit="percentile",
                window=None,
                source_table="score_component_value",
                source_ref=f"{value.id}:percentile_rank",
                as_of=component_as_of,
                data_age_days=value.data_age_days,
            ),
            _evidence(
                evidence_id=f"{prefix}:points",
                kind="statistic",
                label="Risk points",
                value=_number(value.points),
                unit="points",
                window=None,
                source_table="score_component_value",
                source_ref=f"{value.id}:points",
                as_of=component_as_of,
                data_age_days=value.data_age_days,
            ),
            _evidence(
                evidence_id=f"{prefix}:status",
                kind="statistic",
                label="Status",
                value=value.status,
                unit=None,
                window=None,
                source_table="score_component_value",
                source_ref=f"{value.id}:status",
                as_of=component_as_of,
                data_age_days=value.data_age_days,
            ),
            _evidence(
                evidence_id=f"{prefix}:data_age_days",
                kind="statistic",
                label="Data age",
                value=value.data_age_days,
                unit="days",
                window=None,
                source_table="score_component_value",
                source_ref=f"{value.id}:data_age_days",
                as_of=component_as_of,
                data_age_days=value.data_age_days,
            ),
            _evidence(
                evidence_id=f"score_component_definition:{definition.id}:direction",
                kind="config",
                label="Direction",
                value=definition.direction,
                unit=None,
                window=None,
                source_table="score_component_definition",
                source_ref=f"{definition.id}:direction",
                as_of=run.as_of_date,
                data_age_days=None,
            ),
            _evidence(
                evidence_id=f"model_config:{config_ref}:weight:{subject.component_key}",
                kind="config",
                label="Component weight",
                value=weight,
                unit="weight",
                window=None,
                source_table="model_config"
                if model_config is not None
                else "score_component_definition",
                source_ref=f"{config_ref}:component_weights.{subject.component_key}",
                as_of=run.as_of_date,
                data_age_days=None,
            ),
        ]
        window_keys = (
            ("observations", "observations"),
            ("paired_observations", "paired observations"),
            ("window_days", "days"),
            ("lookback_days", "days"),
            ("n_quarters", "quarters"),
        )
        for key, unit in window_keys:
            window_value = value.evidence_ref.get(key)
            if isinstance(window_value, (int, float)):
                evidence.append(
                    _evidence(
                        evidence_id=f"{prefix}:evidence_ref.{key}",
                        kind="statistic",
                        label="Calculation window",
                        value=window_value,
                        unit=unit,
                        window=f"{window_value} {unit}",
                        source_table="score_component_value",
                        source_ref=f"{value.id}:evidence_ref.{key}",
                        as_of=component_as_of,
                        data_age_days=value.data_age_days,
                    )
                )
                break
        return evidence

    def compose(
        self,
        evidence: list[Evidence],
        config: dict[str, Any],
        template_version: str,
        subject: object,
    ) -> ExplanationPayload:
        if not isinstance(subject, ComponentSubject):
            raise TypeError("risk component explainer requires ComponentSubject")
        component_config = config.get("component")
        if not isinstance(component_config, dict):
            raise ValueError("explain_templates.component must be an object")
        by_label = {item.label: item for item in evidence}
        raw = by_label["Raw value"]
        percentile = by_label["Percentile rank"]
        points = by_label["Risk points"]
        status = by_label["Status"]
        age = by_label["Data age"]
        direction = by_label["Direction"]
        weight = by_label["Component weight"]
        window = by_label.get("Calculation window")
        component_label = by_label["Component label"]
        display_name = str(component_label.value)
        values: dict[str, object] = {
            "symbol": subject.symbol.upper(),
            "component_label": display_name,
            "raw_value": raw.value,
            "unit_suffix": f" {raw.unit}" if raw.unit else "",
            "percentile": percentile.value,
            "points": points.value,
            "status": status.value,
            "data_age_days": age.value,
            "direction_label": direction_label(str(direction.value)),
            "weight": weight.value,
            "window": window.window if window else None,
        }
        summary_templates = component_config.get("summary_templates", {})
        detail_templates = component_config.get("detail_templates", {})
        if not isinstance(summary_templates, dict) or not isinstance(detail_templates, dict):
            raise ValueError("component sentence templates must be objects")

        summary_candidates = [
            build_sentence(
                str(summary_templates.get("value", "")), values, [raw.evidence_id], config
            ),
            build_sentence(
                str(summary_templates.get("percentile", "")),
                values,
                [percentile.evidence_id],
                config,
            ),
            build_sentence(
                str(summary_templates.get("points", "")), values, [points.evidence_id], config
            ),
        ]
        detail_candidates = [
            build_sentence(
                str(detail_templates.get("direction_weight", "")),
                values,
                [direction.evidence_id, weight.evidence_id],
                config,
            ),
            build_sentence(
                str(detail_templates.get("status_age", "")),
                values,
                [status.evidence_id, age.evidence_id],
                config,
            ),
        ]
        if window is not None:
            detail_candidates.append(
                build_sentence(
                    str(detail_templates.get("window", "")), values, [window.evidence_id], config
                )
            )
        valid_ids = {item.evidence_id for item in evidence}
        summary = evidence_bound_sentences(
            [item for item in summary_candidates if item is not None], valid_ids, config
        )
        details = evidence_bound_sentences(
            [item for item in detail_candidates if item is not None], valid_ids, config
        )
        confidence_level = (
            "high"
            if status.value == "ok"
            else "low"
            if status.value in {"stale", "missing", "insufficient"}
            else "medium"
        )
        confidence_sentence = ExplanationSentence(
            text=(
                f"Explanation confidence is {confidence_level} because the stored "
                f"component status is {status.value}."
            ),
            evidence_ids=[status.evidence_id],
        )
        confidence_reasons = evidence_bound_sentences([confidence_sentence], valid_ids, config)
        limitations = config.get("limitations", [])
        if not isinstance(limitations, list) or not all(
            isinstance(item, str) for item in limitations
        ):
            raise ValueError("explain template limitations must be a string list")
        disclaimer = config.get("disclaimer")
        if not isinstance(disclaimer, str):
            raise ValueError("explain template disclaimer must be a string")
        headline_template = component_config.get("headline")
        if not isinstance(headline_template, str):
            raise ValueError("component headline template must be a string")
        return ExplanationPayload(
            headline=headline_template.format(**values),
            summary_points=summary,
            sections=[
                ExplanationSection(
                    key="component_details",
                    title="Stored component evidence",
                    sentences=details,
                )
            ],
            evidence=evidence,
            limitations=list(limitations),
            confidence=ExplanationConfidence(
                level=confidence_level,
                reasons=confidence_reasons,
            ),
            data_age=ExplanationDataAge(
                days=age.value if isinstance(age.value, int) else None,
                as_of=raw.as_of,
                status=str(status.value),
            ),
            template_version=template_version,
            subject=ExplanationSubject(type=self.subject_type, key=subject.key),
            disclaimer=disclaimer,
        )


registry.register(RiskComponentExplainer())
