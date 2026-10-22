"""Adapt locally scored articles to the existing portfolio news contract."""

from datetime import UTC, datetime
from typing import Any

from backend.app.news.collection_router import get_news_service
from backend.app.news.exposure_aggregator import ExposureAggregator
from backend.app.news.publication_window import MARKET_TIMEZONE
from backend.app.news.schemas import (
    NewsArticleCard,
    NewsEntityMatchSchema,
    NewsSignalSchema,
    PortfolioNewsIntelligence,
)


def cached_cards(holdings: list[dict[str, Any]]) -> list[NewsArticleCard]:
    held = {str(h["symbol"]).upper(): h for h in holdings}
    cards = []
    for article in get_news_service().feed()["articles"]:
        affected = [symbol for symbol in article["companies"] if symbol in held]
        if holdings and not affected:
            continue
        signals = [
            NewsSignalSchema(
                symbol=symbol,
                sentiment_score=score["score"],
                sentiment_label=score["label"],
                sentiment_confidence=score["confidence"],
                model_name="FinBERT (local)",
                model_version=score["model"],
                processing_time_ms=0,
                event_category="uncertain",
                event_confidence=0,
            )
            for symbol, score in article["companies"].items()
        ]
        cards.append(
            NewsArticleCard(
                id=article["content_hash"][:32],
                source_id=article["content_hash"][:16],
                url=article["url"],
                headline=article["title"],
                publisher=article["publisher"],
                published_at=article["published_at"] or "",
                retrieved_at=article["retrieved_at"],
                snippet=article["excerpt"],
                signals=signals,
                entities=[
                    NewsEntityMatchSchema(
                        symbol=s, company_name=s, match_type="company_name", confidence=1.0
                    )
                    for s in article["companies"]
                ],
                affected_holdings=affected,
                holding_exposure_weight_pct=min(
                    100, sum(float(held[s].get("weight") or 0) * 100 for s in affected)
                ),
                what_the_news_is=article["excerpt"],
                explanation="Local FinBERT sentiment on company-specific passages. "
                "Unknown publication dates are excluded from dated aggregates.",
            )
        )
    return cards


def cached_portfolio_intelligence(holdings: list[dict[str, Any]]) -> PortfolioNewsIntelligence:
    state = get_news_service().status()
    cards = cached_cards(holdings)
    score, label, summaries = ExposureAggregator().aggregate_portfolio_exposure(holdings, cards)
    now = datetime.now(UTC).isoformat()
    return PortfolioNewsIntelligence(
        as_of=state["last_success_at"] or now,
        data_cutoff=datetime.now(MARKET_TIMEZONE).date().isoformat(),
        provider_name="Firecrawl + local FinBERT",
        provider_status="configured" if state["configured"] else "not_configured",
        provider_disclaimer="Cached public publisher articles. Sentiment describes text, "
        "not future stock returns. Refresh in News Intelligence.",
        total_articles_tracked=len(cards),
        deduplicated_article_count=len(cards),
        ambiguous_match_count=0,
        portfolio_sentiment_score=score,
        portfolio_sentiment_label=label,
        holding_summaries=summaries,
        verified_articles=cards[:25],
    )
