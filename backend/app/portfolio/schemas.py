from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

InputMode = Literal["quantities", "weights"]


class PortfolioRowInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    value: Decimal = Field(gt=0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be blank")
        return normalized


class PortfolioPreviewRequest(BaseModel):
    input_mode: InputMode
    rows: list[PortfolioRowInput] = Field(min_length=1, max_length=201)


class PortfolioCreateRequest(PortfolioPreviewRequest):
    name: str = Field(min_length=1, max_length=120)
    preview_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("name cannot be blank")
        return normalized


class PortfolioArchiveRequest(BaseModel):
    archived: bool


class PreviewHolding(BaseModel):
    security_id: UUID
    symbol: str
    company_name: str
    industry: str | None
    value: Decimal


class PortfolioPreviewResponse(BaseModel):
    valid: bool
    input_mode: InputMode
    valuation_date: date | None
    holdings: list[PreviewHolding]
    cash_value: Decimal
    errors: list[str]
    warnings: list[str]
    preview_fingerprint: str | None


class PortfolioSummary(BaseModel):
    id: UUID
    name: str
    input_mode: InputMode
    currency: str
    archived_at: datetime | None
    latest_snapshot_id: UUID
    valuation_date: date
    holding_count: int
    created_at: datetime
    updated_at: datetime


class PortfolioDetail(PortfolioSummary):
    owner_id: UUID
    cash_value: Decimal
    holdings: list[PreviewHolding]


class AuditEventResponse(BaseModel):
    id: UUID
    event_type: str
    entity_type: str
    entity_id: UUID
    details: dict[str, object]
    created_at: datetime
