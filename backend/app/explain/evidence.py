"""Typed evidence items; explanation text may only refer to these stored facts."""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class Evidence(BaseModel):
    evidence_id: str
    kind: Literal["statistic", "rule", "event", "config"]
    label: str
    value: str | int | float | bool | None
    unit: str | None = None
    window: str | None = None
    source_table: str
    source_ref: str
    as_of: date
    data_age_days: int | None = None
