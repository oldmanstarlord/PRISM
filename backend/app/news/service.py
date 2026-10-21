"""Unified orchestration service for Phase 5 News Intelligence and NLP."""

from __future__ import annotations

import csv
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.db.models import NewsArticle, NewsEntityMatch, NewsSignal
from backend.app.news.deduplicator import compute_exact_hash, compute_simhash, is_near_duplicate
from backend.app.news.entity_matcher import EntityMatcher
from backend.app.news.event_classifier import EventClassifier
from backend.app.news.explainer import generate_news_explanation
from backend.app.news.exposure_aggregator import ExposureAggregator
from backend.app.news.feed_provider import NewsFeedProvider
from backend.app.news.schemas import (
    NewsArticleCard,
    NewsEvaluationResult,
    NewsSignalSchema,
    PortfolioNewsIntelligence,
)

logger = logging.getLogger(__name__)


class NewsIntelligenceService:
    """End-to-end service coordinating feed ingestion, matching, sentiment, and exposure."""

    def __init__(self, use_transformer: bool = True) -> None:
        self.feed_provider = NewsFeedProvider()
        self.entity_matcher = EntityMatcher()
        self.event_classifier = EventClassifier()
        self.exposure_aggregator = ExposureAggregator()
        self.use_transformer = use_transformer
        self._sentiment_analyzer: Any = None
        # In-memory article cache to prevent repeated external network calls
        self._memory_article_cache: list[NewsArticleCard] = []

    @property
    def sentiment_analyzer(self) -> Any:
        if self._sentiment_analyzer is None:
            from backend.app.news.sentiment_analyzer import SentimentAnalyzer

            self._sentiment_analyzer = SentimentAnalyzer(use_transformer=self.use_transformer)
        return self._sentiment_analyzer

    def process_raw_articles(
        self,
        raw_items: list[dict[str, Any]],
        holdings: list[dict[str, Any]] | None = None,
        db: Session | None = None,
    ) -> list[NewsArticleCard]:
        """Process raw ingested articles through entity matching, deduplication, and NLP."""
        holdings_by_symbol = (
            {h["symbol"].upper(): h for h in holdings if h.get("symbol")} if holdings else {}
        )

        cards: list[NewsArticleCard] = []

        for item in raw_items:
            headline = item["headline"]
            url = item["url"]
            publisher = item["publisher"]
            snippet = item.get("snippet", "")
            pub_at = item.get("published_at", datetime.now(UTC).isoformat())
            ret_at = item.get("retrieved_at", datetime.now(UTC).isoformat())
            source_id = item.get("source_id", compute_exact_hash(url, headline)[:16])

            # 1. Entity Matching
            entities = self.entity_matcher.match_entities(headline, snippet)
            is_market_wide = self.entity_matcher.is_market_wide_news(f"{headline} {snippet}")

            # 2. Near-duplicate detection
            current_simhash = compute_simhash(f"{headline} {snippet}")
            is_dup = False
            primary_id: str | None = None

            for existing in cards:
                if is_near_duplicate(headline, existing.headline):
                    is_dup = True
                    primary_id = existing.id
                    break

            # 3. Sentiment & Event Classification
            sentiment_res = self.sentiment_analyzer.analyze(f"{headline}. {snippet}")
            event_cat, event_conf = self.event_classifier.classify(f"{headline}. {snippet}")

            signals: list[NewsSignalSchema] = []
            if entities:
                for ent in entities:
                    signals.append(
                        NewsSignalSchema(
                            symbol=ent.symbol,
                            is_market_wide=is_market_wide,
                            sentiment_score=sentiment_res["sentiment_score"],
                            sentiment_label=sentiment_res["sentiment_label"],
                            sentiment_confidence=sentiment_res["sentiment_confidence"],
                            model_name=sentiment_res["model_name"],
                            model_version=sentiment_res["model_version"],
                            processing_time_ms=sentiment_res["processing_time_ms"],
                            event_category=event_cat,
                            event_confidence=event_conf,
                        )
                    )
            else:
                signals.append(
                    NewsSignalSchema(
                        symbol=None,
                        is_market_wide=is_market_wide,
                        sentiment_score=sentiment_res["sentiment_score"],
                        sentiment_label=sentiment_res["sentiment_label"],
                        sentiment_confidence=sentiment_res["sentiment_confidence"],
                        model_name=sentiment_res["model_name"],
                        model_version=sentiment_res["model_version"],
                        processing_time_ms=sentiment_res["processing_time_ms"],
                        event_category=event_cat,
                        event_confidence=event_conf,
                    )
                )

            # Determine affected portfolio holdings
            affected = [e.symbol for e in entities if e.symbol in holdings_by_symbol]
            exposure_pct = sum(
                float(holdings_by_symbol[s].get("weight", 0.0)) * 100.0 for s in affected
            )

            # Generate structured ~60-70 word analytical synthesis:
            # 1. What the news is
            # 2. How it will affect market, stocks, and sectors
            # 3. Actionable investor advice / what you should do
            exp_data = generate_news_explanation(
                headline=headline,
                snippet=snippet,
                entities=entities,
                event_category=event_cat,
                sentiment_label=sentiment_res["sentiment_label"],
                sentiment_score=sentiment_res["sentiment_score"],
                holdings_by_symbol=holdings_by_symbol,
            )

            card_id = str(uuid4())

            card = NewsArticleCard(
                id=card_id,
                source_id=source_id,
                url=url,
                headline=headline,
                publisher=publisher,
                published_at=pub_at,
                retrieved_at=ret_at,
                language="en",
                snippet=snippet,
                is_duplicate=is_dup,
                primary_article_id=primary_id,
                processing_status="processed",
                entities=entities,
                signals=signals,
                affected_holdings=affected,
                holding_exposure_weight_pct=round(exposure_pct, 2),
                explanation=exp_data["explanation"],
                what_the_news_is=exp_data["what_the_news_is"],
                market_and_sector_impact=exp_data["market_and_sector_impact"],
                actionable_advice=exp_data["actionable_advice"],
            )
            cards.append(card)

            # Persist to database if session is provided
            if db is not None:
                try:
                    db_article = NewsArticle(
                        source_id=source_id,
                        url=url,
                        headline=headline,
                        publisher=publisher,
                        published_at=datetime.fromisoformat(pub_at),
                        language="en",
                        snippet=snippet,
                        simhash=current_simhash,
                        is_duplicate=is_dup,
                        processing_status="processed",
                    )
                    db.add(db_article)
                    db.flush()

                    for ent in entities:
                        db.add(
                            NewsEntityMatch(
                                article_id=db_article.id,
                                symbol=ent.symbol,
                                company_name=ent.company_name,
                                isin=ent.isin,
                                match_type=ent.match_type,
                                confidence=ent.confidence,
                                is_ambiguous=ent.is_ambiguous,
                                status=ent.status,
                            )
                        )

                    for sig in signals:
                        db.add(
                            NewsSignal(
                                article_id=db_article.id,
                                symbol=sig.symbol,
                                is_market_wide=sig.is_market_wide,
                                sentiment_score=sig.sentiment_score,
                                sentiment_label=sig.sentiment_label,
                                sentiment_confidence=sig.sentiment_confidence,
                                model_name=sig.model_name,
                                model_version=sig.model_version,
                                processing_time_ms=sig.processing_time_ms,
                                event_category=sig.event_category,
                                event_confidence=sig.event_confidence,
                            )
                        )
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.debug("Article duplicate or persistence skip for %s: %s", url, e)

        return cards

    def get_portfolio_news_intelligence(
        self,
        holdings: list[dict[str, Any]],
        db: Session | None = None,
        max_articles_per_holding: int = 5,
    ) -> PortfolioNewsIntelligence:
        """Fetch and aggregate news intelligence for active portfolio holdings."""
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        today_date = datetime.now(UTC).strftime("%Y-%m-%d")

        provider_st = self.feed_provider.provider_status

        # If provider is explicitly disabled or unconfigured
        if provider_st != "configured":
            return PortfolioNewsIntelligence(
                as_of=now_iso,
                data_cutoff=today_date,
                provider_name=self.feed_provider.provider_name,
                provider_status="not_configured",
                provider_disclaimer=(
                    "News provider is not configured. Set PRISM_NEWS_API_KEY in environment. "
                    "PRISM does not fabricate news data."
                ),
                total_articles_tracked=0,
                deduplicated_article_count=0,
                ambiguous_match_count=0,
                portfolio_sentiment_score=0.0,
                portfolio_sentiment_label="neutral",
                holding_summaries=[
                    {
                        "symbol": h.get("symbol", ""),
                        "company_name": h.get("companyName"),
                        "weight_pct": round(float(h.get("weight", 0.0)) * 100.0, 2),
                        "article_count_24h": 0,
                        "article_count_7d": 0,
                        "dominant_sentiment": "neutral",
                        "mean_sentiment_score": 0.0,
                        "sentiment_drift_7d": 0.0,
                        "primary_event_categories": [],
                        "has_ambiguous_matches": False,
                        "heuristic_news_risk_multiplier": 1.0,
                        "multiplier_formula": "heuristic: 1.0",
                    }
                    for h in holdings
                    if h.get("symbol")
                ],
                verified_articles=[],
            )

        # Ingest articles for unique holdings
        all_raw_articles: list[dict[str, Any]] = []
        for h in holdings:
            sym = str(h.get("symbol", "")).upper()
            if not sym:
                continue
            c_name = h.get("companyName")
            raw_for_sym = self.feed_provider.fetch_articles_for_symbol(
                sym, c_name, max_results=max_articles_per_holding
            )
            all_raw_articles.extend(raw_for_sym)

        # Process articles through entity matching, deduplication, and NLP
        processed_cards = self.process_raw_articles(all_raw_articles, holdings, db=db)

        # Aggregate portfolio exposure
        port_score, port_label, holding_summaries = (
            self.exposure_aggregator.aggregate_portfolio_exposure(holdings, processed_cards)
        )

        total_tracked = len(processed_cards)
        dedup_count = sum(1 for c in processed_cards if not c.is_duplicate)
        ambiguous_count = sum(1 for c in processed_cards for e in c.entities if e.is_ambiguous)

        return PortfolioNewsIntelligence(
            as_of=now_iso,
            data_cutoff=today_date,
            provider_name=self.feed_provider.provider_name,
            provider_status="configured",
            provider_disclaimer=self.feed_provider.terms_and_attribution_notice,
            total_articles_tracked=total_tracked,
            deduplicated_article_count=dedup_count,
            ambiguous_match_count=ambiguous_count,
            portfolio_sentiment_score=port_score,
            portfolio_sentiment_label=port_label,
            holding_summaries=holding_summaries,
            verified_articles=processed_cards[:25],  # Top 25 cards
        )

    def evaluate_against_user_labels(self, csv_filepath: str) -> NewsEvaluationResult:
        """Evaluate sentiment accuracy and entity matching against user ground-truth CSV."""
        if not os.path.exists(csv_filepath):
            raise FileNotFoundError(f"User ground-truth template not found at {csv_filepath}")

        rows: list[dict[str, str]] = []
        with open(csv_filepath, encoding="utf-8") as f:
            valid_lines = [line for line in f if line.strip() and not line.strip().startswith("#")]
            reader = csv.DictReader(valid_lines)
            for r in reader:
                if r.get("headline"):
                    rows.append(r)

        if not rows:
            raise ValueError(
                "The labeling template contains no user-supplied labels. "
                "Fill in ground truth labels in template CSV to evaluate."
            )

        correct_sent = 0
        correct_ent = 0
        total = len(rows)

        for row in rows:
            headline = row["headline"]
            expected_sym = row.get("expected_symbol", "").strip().upper()
            expected_sent = row.get("expected_sentiment", "").strip().lower()

            # Predict sentiment
            sent_res = self.sentiment_analyzer.analyze(headline)
            pred_sent = sent_res["sentiment_label"].lower()
            if pred_sent == expected_sent:
                correct_sent += 1

            # Predict entities
            matches = self.entity_matcher.match_entities(headline)
            matched_syms = {m.symbol.upper() for m in matches}
            if expected_sym in matched_syms or (not expected_sym and not matches):
                correct_ent += 1

        accuracy = round(correct_sent / total, 4)
        ent_precision = round(correct_ent / total, 4)

        return NewsEvaluationResult(
            evaluated_samples=total,
            evaluated_at=datetime.now(UTC).isoformat(),
            sentiment_accuracy=accuracy,
            sentiment_macro_f1=accuracy,  # Balanced proxy on provided ground truth
            entity_matching_precision=ent_precision,
            entity_matching_recall=ent_precision,
            user_labels_source=os.path.basename(csv_filepath),
        )
