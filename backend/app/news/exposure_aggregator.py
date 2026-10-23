"""Portfolio exposure aggregation for verified news signals without double counting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.news.publication_window import published_datetime
from backend.app.news.schemas import (
    EventCategory,
    HoldingNewsSummary,
    NewsArticleCard,
    SentimentLabel,
)


class ExposureAggregator:
    """Aggregates news exposure across portfolio holdings avoiding duplicate contamination."""

    def aggregate_portfolio_exposure(
        self,
        holdings: list[dict[str, Any]],
        articles: list[NewsArticleCard],
    ) -> tuple[float, SentimentLabel, list[HoldingNewsSummary]]:
        """Compute portfolio sentiment and per-holding news exposure metrics."""
        now = datetime.now(UTC)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)

        holdings_by_symbol = {h["symbol"].upper(): h for h in holdings if h.get("symbol")}
        articles_by_symbol: dict[str, list[NewsArticleCard]] = {
            sym: [] for sym in holdings_by_symbol
        }

        # Filter out duplicates to strictly avoid double-counting syndicated reprints
        unique_articles = [a for a in articles if not a.is_duplicate]

        for art in unique_articles:
            for entity in art.entities:
                sym = entity.symbol.upper()
                if sym in articles_by_symbol:
                    articles_by_symbol[sym].append(art)

        holding_summaries: list[HoldingNewsSummary] = []
        weighted_sentiment_sum = 0.0
        total_covered_weight = 0.0

        for sym, h in holdings_by_symbol.items():
            sym_articles = articles_by_symbol[sym]
            weight_val = float(h.get("weight", 0.0))
            weight_pct = round(weight_val * 100.0, 2)

            cnt_24h = 0
            cnt_7d = 0
            context_count = 0
            sentiment_scores: list[float] = []
            recent_scores: list[float] = []
            older_scores: list[float] = []
            events: set[EventCategory] = set()
            has_ambiguous = False

            for a in sym_articles:
                pub_dt = published_datetime(a.published_at)
                if pub_dt is None:
                    continue  # Unknown publication dates are not fresh news.

                if pub_dt < cutoff_7d and a.is_retained_context:
                    until = published_datetime(a.relevance_until)
                    if until and until > now:
                        context_count += 1
                if pub_dt < cutoff_7d or pub_dt > now:
                    continue

                if pub_dt >= cutoff_24h:
                    cnt_24h += 1
                if pub_dt >= cutoff_7d:
                    cnt_7d += 1

                for sig in a.signals:
                    if sig.symbol == sym or sig.is_market_wide:
                        sentiment_scores.append(sig.sentiment_score)
                        events.add(sig.event_category)
                        if pub_dt >= now - timedelta(days=3):
                            recent_scores.append(sig.sentiment_score)
                        else:
                            older_scores.append(sig.sentiment_score)

                for ent in a.entities:
                    if ent.symbol == sym and ent.is_ambiguous:
                        has_ambiguous = True

            mean_sentiment = (
                round(sum(sentiment_scores) / len(sentiment_scores), 4) if sentiment_scores else 0.0
            )

            # 7-day sentiment drift
            recent_avg = (
                sum(recent_scores) / len(recent_scores) if recent_scores else mean_sentiment
            )
            older_avg = sum(older_scores) / len(older_scores) if older_scores else mean_sentiment
            sentiment_drift = round(recent_avg - older_avg, 4)

            # Dominant sentiment classification
            if not sentiment_scores:
                dominant_sent: SentimentLabel = "neutral"
            elif mean_sentiment > 0.15:
                dominant_sent = "positive"
            elif mean_sentiment < -0.15:
                dominant_sent = "negative"
            else:
                dominant_sent = "neutral"

            # Heuristic news risk multiplier (isolated from quantitative market risk)
            heuristic_multiplier = round(1.0 + max(0.0, -mean_sentiment * 0.30), 2)
            heuristic_multiplier = max(0.70, min(1.30, heuristic_multiplier))

            summary = HoldingNewsSummary(
                symbol=sym,
                company_name=h.get("companyName"),
                weight_pct=weight_pct,
                article_count_24h=cnt_24h,
                article_count_7d=cnt_7d,
                retained_context_count=context_count,
                dominant_sentiment=dominant_sent,
                mean_sentiment_score=mean_sentiment,
                sentiment_drift_7d=sentiment_drift,
                primary_event_categories=sorted(list(events)),
                has_ambiguous_matches=has_ambiguous,
                heuristic_news_risk_multiplier=heuristic_multiplier,
            )
            holding_summaries.append(summary)

            if sentiment_scores and weight_val > 0.0:
                weighted_sentiment_sum += mean_sentiment * weight_val
                total_covered_weight += weight_val

        # Portfolio-level weighted sentiment
        portfolio_sentiment = (
            round(weighted_sentiment_sum / total_covered_weight, 4)
            if total_covered_weight > 0.0
            else 0.0
        )

        if portfolio_sentiment > 0.15:
            port_label: SentimentLabel = "positive"
        elif portfolio_sentiment < -0.15:
            port_label = "negative"
        else:
            port_label = "neutral"

        return portfolio_sentiment, port_label, holding_summaries
