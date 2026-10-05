"""Pydantic schemas for corporate announcements and explainable events (D3, D5)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_document_id: UUID | None = None
    security_id: UUID
    symbol: str | None = None
    company_name: str | None = None
    event_type: str
    event_type_method: str
    published_at: datetime
    effective_trading_date: date
    importance: float = Field(..., ge=1.0, le=10.0)
    importance_components: dict[str, Any] = Field(default_factory=dict)
    headline: str | None = None
    source_url: str | None = None

    # Text score / FinBERT details
    sentiment: str | None = None
    p_pos: float | None = None
    p_neg: float | None = None
    p_neu: float | None = None
    evidence_span: str | None = None
    scored_at: datetime | None = None
    model_name: str | None = None
    model_version: str | None = None


class StockEventsResponse(BaseModel):
    symbol: str
    company_name: str
    total_events: int
    events: list[EventItemOut]
    disclaimer: str = (
        "Markets may have already priced this in. PRISM event signals are descriptive "
        "risk indicators and not investment advice or price forecasts."
    )


class RecentEventsResponse(BaseModel):
    total: int
    events: list[EventItemOut]
    disclaimer: str = (
        "Markets may have already priced this in. PRISM event signals are descriptive "
        "risk indicators and not investment advice or price forecasts."
    )
