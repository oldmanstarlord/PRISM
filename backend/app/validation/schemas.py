"""Typed API schemas for persisted validation evidence."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ValidationResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    metric_key: str
    component_key: str
    value: float | None
    baseline_value: float | None
    n: int
    period: str


class ValidationRunSummaryOut(BaseModel):
    id: UUID
    kind: str
    config_fingerprint: str
    period: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    notes: dict[str, object] = Field(default_factory=dict)


class ValidationRunDetailOut(ValidationRunSummaryOut):
    results: list[ValidationResultOut] = Field(default_factory=list)
