"""Pydantic schemas for multi-user Journal persistence."""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JournalNoteCreateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID | None = None
    symbol: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        norm = value.strip().upper()
        if not norm:
            raise ValueError("symbol cannot be blank")
        return norm


class JournalNoteResponse(BaseModel):
    id: UUID
    owner_id: UUID
    symbol: str
    content: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


DecisionTypeLiteral = Literal[
    "BUY", "HOLD", "SELL", "REVIEW",
    "Buy", "Hold", "Sell", "Review",
]


class JournalDecisionCreateInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID | None = None
    symbol: str = Field(min_length=1, max_length=40)
    decision_type: DecisionTypeLiteral
    decision_date: date
    rationale: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)
    snapshot_id: UUID | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        norm = value.strip().upper()
        if not norm:
            raise ValueError("symbol cannot be blank")
        return norm

    @field_validator("decision_type")
    @classmethod
    def normalize_decision_type(cls, value: str) -> str:
        return value.strip().upper()


class JournalDecisionResponse(BaseModel):
    id: UUID
    owner_id: UUID
    symbol: str
    decision_type: str
    decision_date: date
    rationale: str
    tags: list[str]
    snapshot: dict[str, Any]
    snapshot_id: UUID | None
    created_at: datetime
    updated_at: datetime


class JournalSyncRequest(BaseModel):
    notes: list[JournalNoteCreateInput] = Field(default_factory=list)
    decisions: list[JournalDecisionCreateInput] = Field(default_factory=list)


class JournalSyncResponse(BaseModel):
    notes_synced: int
    decisions_synced: int
