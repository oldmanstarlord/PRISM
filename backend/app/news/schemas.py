"""Pydantic schemas for Phase 5 News Intelligence and NLP."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NewsRequestModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


SentimentLabel = Literal["positive", "neutral", "negative", "uncertain"]
EventCategory = Literal[
    "earnings",
    "guidance",
    "dividend",
    "m&a",
    "regulation",
    "litigation",
    "product",
    "macro",
    "routine_coverage",
    "uncertain",
]
MatchStatus = Literal["auto_matched", "needs_review", "confirmed", "rejected"]
MatchType = Literal["exact_symbol", "company_name", "alias", "isin", "market_wide"]


class HoldingInputSchema(NewsRequestModel):
    """Input representation of a holding for news evaluation."""

    symbol: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9&.-]+$")
    companyName: str | None = Field(default=None, max_length=255)
    sector: str | None = Field(default=None, max_length=160)
    quantity: float = Field(default=1.0, gt=0)
    buyPrice: float = Field(default=1.0, gt=0)
    weight: float | None = Field(default=None, ge=0.0, le=1.0)


class NewsPortfolioRequest(NewsRequestModel):
    """Request payload for portfolio-level news intelligence."""

    holdings: list[HoldingInputSchema] = Field(min_length=1, max_length=150)


class NewsEntityMatchSchema(BaseModel):
    """Matched security entity with ambiguity and confidence metrics."""

    symbol: str
    company_name: str
    isin: str | None = None
    match_type: MatchType
    confidence: float = Field(ge=0.0, le=1.0)
    is_ambiguous: bool = False
    status: MatchStatus = "auto_matched"
    ambiguity_reason: str | None = None


class NewsSignalSchema(BaseModel):
    """Sentiment and event classification output for an article."""

    symbol: str | None = None
    is_market_wide: bool = False
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    sentiment_label: SentimentLabel
    sentiment_confidence: float = Field(ge=0.0, le=1.0)
    model_name: str
    model_version: str
    processing_time_ms: float
    event_category: EventCategory
    event_confidence: float = Field(ge=0.0, le=1.0)


class NewsArticleCard(BaseModel):
    """User-facing news article card with verified source attribution."""

    id: str
    source_id: str
    url: str
    headline: str
    publisher: str
    published_at: str  # ISO-8601 with timezone
    retrieved_at: str  # ISO-8601 with timezone
    language: str = "en"
    snippet: str | None = None
    is_duplicate: bool = False
    primary_article_id: str | None = None
    processing_status: str = "processed"
    entities: list[NewsEntityMatchSchema] = Field(default_factory=list)
    signals: list[NewsSignalSchema] = Field(default_factory=list)
    affected_holdings: list[str] = Field(default_factory=list)
    holding_exposure_weight_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    explanation: str = Field(default="")
    what_the_news_is: str = Field(default="")
    market_and_sector_impact: str = Field(default="")
    actionable_advice: str = Field(default="")


class HoldingNewsSummary(BaseModel):
    """Aggregated verified news signals for a specific portfolio holding."""

    symbol: str
    company_name: str | None = None
    weight_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    article_count_24h: int = Field(ge=0, default=0)
    article_count_7d: int = Field(ge=0, default=0)
    dominant_sentiment: SentimentLabel = "neutral"
    mean_sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    sentiment_drift_7d: float = 0.0
    primary_event_categories: list[EventCategory] = Field(default_factory=list)
    has_ambiguous_matches: bool = False
    heuristic_news_risk_multiplier: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description=(
            "Heuristic sentiment multiplier; strictly isolated from quantitative market risk."
        ),
    )
    multiplier_formula: str = (
        "heuristic: 1.0 + max(0.0, -mean_sentiment_score * 0.3) if negative else 1.0"
    )


class PortfolioNewsIntelligence(BaseModel):
    """Authoritative response for the portfolio News Intelligence tab."""

    as_of: str
    data_cutoff: str
    provider_name: str
    provider_status: Literal["configured", "not_configured", "rate_limited", "feed_unavailable"]
    provider_disclaimer: str
    total_articles_tracked: int
    deduplicated_article_count: int
    ambiguous_match_count: int
    portfolio_sentiment_score: float = Field(ge=-1.0, le=1.0)
    portfolio_sentiment_label: SentimentLabel
    holding_summaries: list[HoldingNewsSummary] = Field(default_factory=list)
    verified_articles: list[NewsArticleCard] = Field(default_factory=list)
    methodology_disclaimer: str = (
        "News Intelligence is diagnostic and isolated. News sentiment and event classifications "
        "do NOT alter historical covariance, volatility, or market risk scores. "
        "Any joint indicators are labelled heuristic with formulas displayed. "
        "Zero price-direction predictions or trade recommendations are made."
    )


class NewsEvaluationResult(BaseModel):
    """Evaluation scorecard calculated strictly against user-provided ground truth labels."""

    evaluated_samples: int
    evaluated_at: str
    sentiment_accuracy: float
    sentiment_macro_f1: float
    entity_matching_precision: float
    entity_matching_recall: float
    user_labels_source: str
    governance_notice: str = (
        "Evaluated strictly against user-supplied ground truth labels. No labels were fabricated."
    )
