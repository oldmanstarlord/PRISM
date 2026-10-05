"""Typed API contracts for Step 14 operations."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FreshnessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_key: str
    last_success_at: datetime | None
    last_data_date: date | None
    expected_cadence: int
    grace: int
    status: str


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow: str
    code_version: str
    configuration_hash: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    row_counts: dict[str, object]
    quality_summary: dict[str, object]
    error_summary: str | None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    subject_type: str
    subject_id: str
    alert_type: str
    reason: str
    inputs_ref: dict[str, object]
    score: float | None
    status: str
    config_version: str
    config_fingerprint: str


class WatchlistItemInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    thresholds: dict[str, float] = Field(default_factory=dict)


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    items: list[WatchlistItemInput] = Field(default_factory=list)


class WatchlistItemOut(BaseModel):
    id: UUID
    security_id: UUID
    symbol: str
    thresholds: dict[str, object]


class WatchlistOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    items: list[WatchlistItemOut]


class LimitationsOut(BaseModel):
    method_version: str
    price_frequency_label: str
    filings_news_poll_minutes: int
    limitations: list[str]
