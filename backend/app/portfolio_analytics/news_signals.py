"""Modular schema contracts and interface definitions for future news-intelligence integration.

NOTE: As specified in PRISM requirements, news scraping is not executed directly at this stage.
This module establishes strict, versioned data contracts separating news-based qualitative risk
from mathematically defined market-based risk. Future news-ingestion workers will publish into
these schemas without silently altering historical market risk calculations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SentimentLabel = Literal["positive", "neutral", "negative"]


class NewsArticleItem(BaseModel):
    """Normalized schema for individual news articles ingested for a security."""

    id: str = Field(description="Unique article identifier or source hash")
    symbol: str = Field(description="Associated stock ticker symbol")
    headline: str = Field(description="Article title / headline")
    summary: str = Field(description="Brief article excerpt or generated abstract")
    publisher: str = Field(description="Source news outlet or publisher")
    published_at: str = Field(description="ISO-8601 publication timestamp")
    sentiment_score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Normalized polarity score from -1.0 (bearish) to +1.0 (bullish)",
    )
    sentiment_label: SentimentLabel = Field(description="Categorical sentiment label")
    relevance_score: float = Field(
        ge=0.0, le=1.0, description="Confidence of relevance to the company (0.0 to 1.0)"
    )
    source_url: str | None = Field(default=None, description="Canonical source URL")


class StockNewsSignal(BaseModel):
    """Aggregated sentiment, volume, and event indicators for a single stock."""

    symbol: str = Field(description="Stock ticker symbol")
    company_name: str | None = Field(default=None, description="Company name if resolved")
    sentiment_average_7d: float = Field(
        ge=-1.0, le=1.0, description="7-day rolling weighted sentiment mean"
    )
    sentiment_label: SentimentLabel = Field(description="Dominant sentiment classification")
    news_volume_24h: int = Field(ge=0, description="Number of unique articles in last 24 hours")
    news_volume_7d: int = Field(ge=0, description="Number of unique articles in last 7 days")
    sentiment_drift_7d: float = Field(
        description="Sentiment change over 7d (positive = improving, negative = deteriorating)"
    )
    significant_events: list[str] = Field(
        default_factory=list,
        description="Identified corporate events (e.g. Earnings, Regulatory, Management changes)",
    )
    news_risk_multiplier: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Standalone news risk factor (1.0 = neutral); kept decoupled from market risk",
    )
    headline_sample: list[str] = Field(
        default_factory=list, description="Sample of recent representative headlines"
    )
    data_freshness: str = Field(
        default="Mocked Schema Preview", description="Signal ingestion status"
    )


class PortfolioNewsSummary(BaseModel):
    """Portfolio-wide news intelligence aggregation contract."""

    as_of: str = Field(description="Timestamp of signal compilation")
    contract_version: str = Field(default="v1-modular-draft")
    architecture_status: str = Field(
        default="Decoupled - ready for independent news worker integration"
    )
    portfolio_sentiment_average: float = Field(
        ge=-1.0, le=1.0, description="Cap-weighted portfolio sentiment score"
    )
    total_articles_tracked: int = Field(ge=0)
    high_impact_event_count: int = Field(ge=0)
    stock_signals: list[StockNewsSignal] = Field(default_factory=list)
    sample_articles: list[NewsArticleItem] = Field(default_factory=list)
    methodology_disclaimer: str = Field(
        default=(
            "News-derived signals are isolated in a separate analytical layer. "
            "They represent qualitative media discourse and do NOT alter historical "
            "market-risk scores or covariance matrices without documented methodology approval."
        )
    )


def generate_modular_news_preview(
    holdings: list[dict[str, Any]],
) -> PortfolioNewsSummary:
    """Generate contract-compliant news signal previews for a list of portfolio holdings.

    This function provides a preview of the upcoming news-intelligence
    layer, demonstrating exact contract compliance and decoupling from quantitative risk.
    """
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    stock_signals: list[StockNewsSignal] = []
    articles: list[NewsArticleItem] = []

    # Deterministic contract sample generation based on provided holdings
    sentiment_map = {
        0: (0.35, "positive", "Strong quarterly operational momentum and margin expansion"),
        1: (-0.15, "neutral", "Sector-wide commodity cost pressures and pricing scrutiny"),
        2: (0.55, "positive", "Expansion of enterprise contracts and product innovation"),
        3: (-0.40, "negative", "Regulatory query regarding compliance filings"),
        4: (0.10, "neutral", "Stable institutional holding disclosure and steady volume"),
    }

    for idx, h in enumerate(holdings):
        symbol = str(h.get("symbol", "")).upper()
        if not symbol:
            continue

        base_sent, label, event_desc = sentiment_map[idx % len(sentiment_map)]
        # Add slight variation per symbol
        symbol_hash = sum(ord(c) for c in symbol)
        sent = round(base_sent + (symbol_hash % 10 - 5) * 0.02, 2)
        sent = max(-1.0, min(1.0, sent))
        c_label: SentimentLabel = (
            "positive" if sent > 0.20 else ("negative" if sent < -0.20 else "neutral")
        )

        events = [event_desc] if abs(sent) > 0.3 else []

        sig = StockNewsSignal(
            symbol=symbol,
            company_name=h.get("companyName"),
            sentiment_average_7d=sent,
            sentiment_label=c_label,
            news_volume_24h=3 + (symbol_hash % 8),
            news_volume_7d=18 + (symbol_hash % 25),
            sentiment_drift_7d=round((symbol_hash % 7 - 3) * 0.05, 2),
            significant_events=events,
            news_risk_multiplier=round(1.0 + max(0.0, -sent * 0.3), 2),
            headline_sample=[
                f"{symbol}: Market update on quarterly operating performance",
                f"{symbol} features in institutional brokerage sector report",
            ],
            data_freshness="Contract Ready (Phase 3 Interface Preview)",
        )
        stock_signals.append(sig)

        articles.append(
            NewsArticleItem(
                id=f"art-{symbol}-{idx}",
                symbol=symbol,
                headline=f"{symbol}: Analysts review forward guidance and sector positioning",
                summary=f"Analysis of market indicators and operating factors affecting {symbol}.",
                publisher="PRISM Financial News Wire",
                published_at=now_iso,
                sentiment_score=sent,
                sentiment_label=c_label,
                relevance_score=0.92,
                source_url=None,
            )
        )

    avg_sentiment = (
        round(sum(s.sentiment_average_7d for s in stock_signals) / len(stock_signals), 2)
        if stock_signals
        else 0.0
    )

    return PortfolioNewsSummary(
        as_of=now_iso,
        contract_version="v1-modular-draft",
        architecture_status="Decoupled - ready for independent news worker integration",
        portfolio_sentiment_average=avg_sentiment,
        total_articles_tracked=len(articles) * 4,
        high_impact_event_count=sum(len(s.significant_events) for s in stock_signals),
        stock_signals=stock_signals,
        sample_articles=articles[:6],
    )
