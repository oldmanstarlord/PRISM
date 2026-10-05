"""Pydantic schemas for Step 11 news, policy rules, and policy events."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NewsItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    published_at: datetime
    ingested_at: datetime
    headline: str
    url: str
    content_hash: str


class PolicyRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rule_key: str
    description: str
    match_keywords: list[str]
    match_category: str | None
    affected_industries: list[str]
    direction: str
    severity: float
    rationale: str
    reviewer: str
    version: str
    active: bool
    created_at: datetime
    updated_at: datetime


class PolicyRuleUpdate(BaseModel):
    description: str | None = None
    match_keywords: list[str] | None = None
    match_category: str | None = None
    affected_industries: list[str] | None = None
    direction: str | None = None
    severity: float | None = None
    rationale: str = Field(..., min_length=10, description="Mandatory economic rationale")
    reviewer: str = Field(..., min_length=2, description="Mandatory reviewer identifier")
    active: bool | None = None


class PolicyEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    news_item_id: UUID
    rule_id: UUID
    matched_at: datetime
    affected_industry: str
    severity: float
    evidence: dict[str, Any]
    headline: str | None = None
    source: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    rule_key: str | None = None
    rule_description: str | None = None
    direction: str | None = None
    rationale: str | None = None


class StockNewsItemOut(BaseModel):
    news_item: NewsItemOut
    matched_events: list[PolicyEventOut] = []
    # direct_security_mention | industry_policy_match
    relevance_reason: str = "industry_policy_match"


class StockNewsResponse(BaseModel):
    symbol: str
    company_name: str
    industry: str | None
    items: list[StockNewsItemOut]
    macro_pressure_points: float | None = None
    disclaimer: str = (
        "Markets may have already priced this in. PRISM event signals are descriptive "
        "risk indicators and not investment advice or directional forecasts."
    )


class RecentPolicyEventsResponse(BaseModel):
    events: list[PolicyEventOut]
    total_count: int
    disclaimer: str = (
        "Markets may have already priced this in. PRISM event signals are descriptive "
        "risk indicators and not investment advice or directional forecasts."
    )
