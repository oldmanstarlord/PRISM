"""Versioned API payload for every PRISM explainer."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.explain.evidence import Evidence


class ExplanationSentence(BaseModel):
    text: str
    evidence_ids: list[str] = Field(min_length=1)


class ExplanationSection(BaseModel):
    key: str
    title: str
    sentences: list[ExplanationSentence]
    chart_spec: dict[str, object] | None = None


class ExplanationConfidence(BaseModel):
    level: Literal["high", "medium", "low"]
    reasons: list[ExplanationSentence]


class ExplanationDataAge(BaseModel):
    days: int | None
    as_of: date
    status: str


class ExplanationSubject(BaseModel):
    type: str
    key: str


class ExplanationPayload(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    headline: str
    summary_points: list[ExplanationSentence]
    sections: list[ExplanationSection]
    evidence: list[Evidence]
    limitations: list[str]
    confidence: ExplanationConfidence
    data_age: ExplanationDataAge
    template_version: str
    subject: ExplanationSubject
    disclaimer: str
    effective_time: date | None = None
    method: str | None = None
    method_version: str | None = None
    input_fingerprint: str | None = None
    lookback: dict[str, object] | None = None
    units: dict[str, str] = Field(default_factory=dict)
    thresholds: dict[str, object] = Field(default_factory=dict)
    component_contributions: list[dict[str, object]] = Field(default_factory=list)
    data_sufficiency: str | None = None
    computed_at: datetime | None = None


class GlossaryTermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    term_key: str
    label: str
    plain_definition: str
    formula_text: str | None
    see_also: list[str]
    version: str


class ExplanationStoredOut(BaseModel):
    id: str
    payload: ExplanationPayload
    created_at: datetime
    reused: bool
