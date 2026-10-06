"""Typed API contracts for news insights and portfolio overlays."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.data_sources.schemas import DataSourceOut


class NewsImpactPathOut(BaseModel):
    path_type: str
    direction: str
    severity: float
    exposure_score: float
    exposure_band: str
    confidence: float
    evidence: list[dict[str, object]] = Field(min_length=1)


class AffectedStockOut(BaseModel):
    symbol: str | None
    security_id: UUID | None
    industry: str
    direction: str
    exposure_score: float
    exposure_band: str
    confidence: float
    paths: list[NewsImpactPathOut]


class NewsInsightOut(BaseModel):
    news_id: UUID
    headline: str
    source: str
    published_at: datetime
    url: str
    severity: float
    affected_industries: list[str]
    matched_rules: list[str]
    unreviewed: bool
    affected_stocks: list[AffectedStockOut]


class NewsInsightsResponse(BaseModel):
    items: list[NewsInsightOut]
    source_statuses: list[DataSourceOut]
    limitations: list[str]


class PortfolioHoldingImpactOut(BaseModel):
    symbol: str
    industry: str
    weight: float
    risk_contribution: float | None
    exposure_score: float
    exposure_band: str
    cluster_id: str | None


class PortfolioNewsOverlayOut(BaseModel):
    schema_version: str = "1.0"
    portfolio_id: UUID
    news_id: UUID
    as_of: datetime
    affected_industry_weight: float
    holdings: list[PortfolioHoldingImpactOut]
    cluster_overlap: dict[str, list[str]]
    method: str = "news-impact-portfolio-overlay"
    method_version: str = "1.0.0"
    inputs: list[str]
    thresholds: dict[str, object]
    confidence: float
    data_age_days: int
    limitations: list[str]
    disclaimer: str
    predicted_changes: list[object] = Field(default_factory=list)
