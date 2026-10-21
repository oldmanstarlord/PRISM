"""Pydantic schemas for the PRISM Stock Decision Engine.

SELL / HOLD / WAIT & WATCH flags with full explainability.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DecisionFlag = Literal["SELL", "HOLD", "WAIT & WATCH"]
ConfidenceLevel = Literal["high", "medium", "low", "insufficient_data"]


class DecisionRequestModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class DecisionHoldingInput(DecisionRequestModel):
    """A single portfolio holding for decision analysis."""

    symbol: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9&.-]+$")
    company_name: str | None = Field(default=None, max_length=255)
    sector: str | None = Field(default=None, max_length=160)
    quantity: float = Field(default=1.0, gt=0)
    buy_price: float = Field(default=1.0, gt=0)
    weight: float | None = Field(default=None, ge=0.0, le=1.0)


class PortfolioDecisionRequest(DecisionRequestModel):
    """Request body: provide explicit holdings or a saved portfolio_id."""

    holdings: list[DecisionHoldingInput] = Field(min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Component score payloads
# ---------------------------------------------------------------------------


class FundamentalScorePayload(BaseModel):
    """Output from the Fundamental adapter — backed by the five-factor risk score."""

    symbol: str
    fundamental_strength_score: float = Field(
        ge=0.0,
        le=100.0,
        description=(
            "0–100 where 100 = lowest market risk (strongest financial health signal). "
            "Derived by inverting the cross-sectional five-factor risk score."
        ),
    )
    fundamental_classification: str
    raw_risk_score: float | None = Field(
        default=None,
        description="Original persisted five-factor risk score (higher = more risk)",
    )
    anomaly_flag: bool = Field(default=False)
    anomaly_score: float | None = None
    model_source: str = "five_factor_risk_score_inverted"
    model_version: str | None = None
    data_cutoff: Any | None = None
    quality_status: str | None = None
    availability: Literal["available", "unavailable"] = "available"
    failure_reason: str | None = None


class SectorStrengthPayload(BaseModel):
    """Output from the Sector Divergence adapter."""

    symbol: str
    sector: str | None = None
    divergence_value: float | None = Field(
        default=None,
        description="Raw z-score from the sector divergence model (positive = outperforming peers)",
    )
    sector_strength_score: float = Field(
        ge=0.0,
        le=100.0,
        description=(
            "0–100 industry percentile rank from the latest completed sector divergence run. "
            "100 = highest outperformer, 0 = worst underperformer."
        ),
    )
    interpretation: str | None = None
    horizon_days: int = 20
    source: str = "existing_sector_divergence_module"
    availability: Literal["available", "unavailable", "no_run"] = "available"
    failure_reason: str | None = None


class NewsScorePayload(BaseModel):
    """Output from the News Sentiment adapter."""

    symbol: str
    news_score: float = Field(
        ge=0.0,
        le=100.0,
        description=(
            "0–100. Derived from mean_sentiment_score: (score + 1.0) / 2.0 * 100. "
            "50 = neutral fallback when data is insufficient."
        ),
    )
    sentiment: str  # positive / neutral / negative / uncertain
    news_confidence: float = Field(ge=0.0, le=1.0)
    articles_analyzed: int = 0
    major_events: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    provider_status: str = "not_configured"
    is_fallback_neutral: bool = False
    failure_reason: str | None = None


# ---------------------------------------------------------------------------
# Dynamic weight regime
# ---------------------------------------------------------------------------


class AppliedWeights(BaseModel):
    """Weight regime applied during final score calculation."""

    fundamental: float
    sector: float
    news: float
    regime: Literal["normal", "significant_news", "critical_event"]
    regime_reason: str = ""


# ---------------------------------------------------------------------------
# Per-stock decision
# ---------------------------------------------------------------------------


class StockDecision(BaseModel):
    """Full decision result for one portfolio stock."""

    symbol: str
    company_name: str | None = None
    sector: str | None = None

    # Component scores
    fundamental: FundamentalScorePayload
    sector_strength: SectorStrengthPayload
    news: NewsScorePayload

    # Final scoring
    applied_weights: AppliedWeights
    final_score: float = Field(ge=0.0, le=100.0)
    decision: DecisionFlag
    confidence: ConfidenceLevel

    # Explanation
    explanation: str
    reasons: list[str] = Field(default_factory=list)
    risk_alerts: list[str] = Field(default_factory=list)

    # Traceability
    analysis_timestamp: str
    data_freshness: str | None = None

    # Status
    status: Literal["analyzed", "unavailable"] = "analyzed"
    status_reason: str | None = None


# ---------------------------------------------------------------------------
# Portfolio-level summary
# ---------------------------------------------------------------------------


class PortfolioDecisionSummary(BaseModel):
    """Aggregate decision metrics for the entire analyzed portfolio."""

    total_stocks: int
    hold_count: int
    wait_and_watch_count: int
    sell_count: int
    unavailable_count: int
    portfolio_weighted_risk_exposure: float = Field(
        ge=0.0,
        le=100.0,
        description=(
            "Weight-adjusted share (%) of SELL-flagged holdings in the analyzed portfolio."
        ),
    )
    average_final_score: float | None = None
    analysis_timestamp: str


class PortfolioDecisionResponse(BaseModel):
    """Full decision analysis response for a portfolio."""

    governance_disclaimer: str = (
        "PRISM Stock Decision Engine flags represent diagnostic health signals based on "
        "quantitative risk factors, sector divergence, and news sentiment. They are NOT "
        "investment advice, price-direction forecasts, or guaranteed outcomes. "
        "Always conduct independent research before making investment decisions."
    )
    methodology_version: str = "decision-engine-v1"
    summary: PortfolioDecisionSummary
    decisions: list[StockDecision]
