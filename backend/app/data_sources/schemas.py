"""API contracts for the external data-source registry."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_key: str
    dataset: str
    owner: str
    access_method: str
    terms_url: str
    license_note: str
    cadence: str
    expected_grace_days: int
    status: str
    freshness_status: str
    last_verified_at: datetime | None
    last_success_at: datetime | None
    notes: str | None
