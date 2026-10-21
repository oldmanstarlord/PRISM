"""Comprehensive tests for Phase 5 News Intelligence and NLP."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.main import app
from backend.app.news.deduplicator import (
    compute_exact_hash,
    compute_simhash,
    hamming_distance,
    is_near_duplicate,
)
from backend.app.news.entity_matcher import EntityMatcher
from backend.app.news.event_classifier import EventClassifier
from backend.app.news.exposure_aggregator import ExposureAggregator
from backend.app.news.feed_provider import NewsFeedProvider, parse_rfc822_date
from backend.app.news.schemas import (
    NewsArticleCard,
    NewsEntityMatchSchema,
    NewsSignalSchema,
)
from backend.app.news.sentiment_analyzer import SentimentAnalyzer
from backend.app.news.service import NewsIntelligenceService


@pytest.fixture(autouse=True)
def authenticated_news_user():
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=UUID("00000000-0000-0000-0000-000000000001"), email="news-test@prism.local"
    )
    yield
    app.dependency_overrides.pop(require_user, None)


def test_duplicates_and_near_duplicate_detection():
    """Verify exact hash and near-duplicate SimHash / Jaccard detection."""
    headline_1 = "TCS reports 12% rise in quarterly net profit and announces dividend"
    headline_2 = "TCS reports 12% jump in quarterly net profit, announces dividend payout"
    headline_unrelated = "RBI leaves repo rate unchanged at 6.5% during monetary policy review"

    url_1 = "https://economictimes.indiatimes.com/markets/stocks/news/tcs-q3-results/12345"
    url_2 = "https://economictimes.indiatimes.com/markets/stocks/news/tcs-q3-results/12345"

    # Exact hash test
    assert compute_exact_hash(url_1, headline_1) == compute_exact_hash(url_2, headline_2)

    # SimHash test for near-duplicate syndicated reprints
    sh1 = compute_simhash(headline_1)
    sh2 = compute_simhash(headline_2)
    sh_diff = compute_simhash(headline_unrelated)

    assert hamming_distance(sh1, sh2) < hamming_distance(sh1, sh_diff)
    assert is_near_duplicate(headline_1, headline_2) is True
    assert is_near_duplicate(headline_1, headline_unrelated) is False


def test_ambiguous_tickers_and_collision_handling():
    """Verify ticker collision handling for ambiguous words like OIL, BEL, CAN, IDEA."""
    matcher = EntityMatcher()

    # Ambiguous headline: 'oil' used as general commodity, not Oil India Ltd
    text_commodity = "Crude oil prices drop 2% globally as US inventory expands"
    matches_comm = matcher.match_entities(text_commodity)
    # If OIL matches bare token, it MUST be flagged ambiguous and needs_review
    for m in matches_comm:
        if m.symbol == "OIL":
            assert m.is_ambiguous is True
            assert m.status == "needs_review"
            assert m.confidence < 0.50

    # Confirmed company context for Oil India
    text_company = "Oil India Limited reports record quarterly profit and special dividend"
    matches_comp = matcher.match_entities(text_company)
    oil_match = next(m for m in matches_comp if m.symbol == "OIL")
    assert oil_match.is_ambiguous is False
    assert oil_match.status == "auto_matched"
    assert oil_match.confidence >= 0.90


def test_wrong_entity_matches_and_market_wide_detection():
    """Verify that market-wide news is distinguished from company-specific news."""
    matcher = EntityMatcher()

    macro_text = "RBI keeps repo rate unchanged at 6.50% amid food inflation concerns"
    assert matcher.is_market_wide_news(macro_text) is True

    company_text = "Infosys secures $1.5B digital transformation deal with European telecom"
    assert matcher.is_market_wide_news(company_text) is False
    matches = matcher.match_entities(company_text)
    assert any(m.symbol == "INFY" for m in matches)


def test_stale_articles_and_timezones():
    """Verify RFC-822 date parsing across timezones and 24h vs 7d vs stale filtering."""
    # GMT / UTC
    dt_gmt = parse_rfc822_date("Wed, 21 Oct 2026 04:30:00 GMT")
    assert dt_gmt.tzinfo is not None

    # IST offset (+0530)
    dt_ist = parse_rfc822_date("Wed, 21 Oct 2026 10:00:00 +0530")
    assert dt_ist.tzinfo is not None
    assert dt_gmt == dt_ist

    now = datetime.now(UTC)
    aggregator = ExposureAggregator()
    holdings = [{"symbol": "TCS", "weight": 1.0}]

    recent_art = NewsArticleCard(
        id="a1",
        source_id="s1",
        url="https://example.com/tcs-recent",
        headline="TCS quarterly net profit surges",
        publisher="Reuters",
        published_at=(now - timedelta(hours=2)).isoformat(),
        retrieved_at=now.isoformat(),
        entities=[
            NewsEntityMatchSchema(
                symbol="TCS",
                company_name="TCS",
                match_type="exact_symbol",
                confidence=0.9,
                is_ambiguous=False,
                status="auto_matched",
            )
        ],
        signals=[
            NewsSignalSchema(
                symbol="TCS",
                is_market_wide=False,
                sentiment_score=0.5,
                sentiment_label="positive",
                sentiment_confidence=0.8,
                model_name="test",
                model_version="1.0",
                processing_time_ms=1.0,
                event_category="earnings",
                event_confidence=0.8,
            )
        ],
        affected_holdings=["TCS"],
        holding_exposure_weight_pct=100.0,
        explanation="TCS earnings",
    )

    stale_art = NewsArticleCard(
        id="a2",
        source_id="s2",
        url="https://example.com/tcs-stale",
        headline="TCS annual report archived",
        publisher="Reuters",
        published_at=(now - timedelta(days=20)).isoformat(),
        retrieved_at=now.isoformat(),
        entities=[
            NewsEntityMatchSchema(
                symbol="TCS",
                company_name="TCS",
                match_type="exact_symbol",
                confidence=0.9,
                is_ambiguous=False,
                status="auto_matched",
            )
        ],
        signals=[
            NewsSignalSchema(
                symbol="TCS",
                is_market_wide=False,
                sentiment_score=0.0,
                sentiment_label="neutral",
                sentiment_confidence=0.8,
                model_name="test",
                model_version="1.0",
                processing_time_ms=1.0,
                event_category="routine_coverage",
                event_confidence=0.8,
            )
        ],
        affected_holdings=["TCS"],
        holding_exposure_weight_pct=100.0,
        explanation="Stale",
    )

    _, _, summaries = aggregator.aggregate_portfolio_exposure(holdings, [recent_art, stale_art])
    summary_tcs = summaries[0]
    assert summary_tcs.article_count_24h == 1
    assert summary_tcs.article_count_7d == 1  # Stale 20-day article is excluded from 7d count


def test_missing_credentials_and_unconfigured_state():
    """Verify that unconfigured provider returns explicit status and does not fabricate data."""
    with patch.dict(os.environ, {"PRISM_NEWS_ENABLED": "0"}):
        provider = NewsFeedProvider()
        assert provider.provider_status == "not_configured"
        articles = provider.fetch_articles_for_symbol("TCS")
        assert len(articles) == 0

        service = NewsIntelligenceService(use_transformer=False)
        intel = service.get_portfolio_news_intelligence([{"symbol": "TCS", "weight": 1.0}])
        assert intel.provider_status == "not_configured"
        assert len(intel.verified_articles) == 0
        assert intel.total_articles_tracked == 0


def test_low_confidence_sentiment_uncertainty():
    """Verify low-confidence or mixed financial text yields 'uncertain' label, never forced."""
    analyzer = SentimentAnalyzer(use_transformer=False)

    mixed_text = "Operations face volatile market conditions with uncertain revenue outlook"
    res = analyzer.analyze_lexicon_baseline(mixed_text)
    assert res["sentiment_label"] == "uncertain"
    assert res["model_name"] == "lexicon-financial-v1"

    pos_text = "Net profit surges to record high as operating margins beat analyst estimates"
    res_pos = analyzer.analyze_lexicon_baseline(pos_text)
    assert res_pos["sentiment_label"] == "positive"
    assert res_pos["sentiment_score"] > 0.20

    neg_text = "Regulatory probe and penalty notice trigger steep slump in share price"
    res_neg = analyzer.analyze_lexicon_baseline(neg_text)
    assert res_neg["sentiment_label"] == "negative"
    assert res_neg["sentiment_score"] < -0.20


def test_corporate_event_classification():
    """Verify corporate event categorizations across earnings, dividend, m&a, and regulation."""
    classifier = EventClassifier()

    earn_text = "TCS reports Q3 results with net profit beating estimates"
    cat_earn, conf_earn = classifier.classify(earn_text)
    assert cat_earn == "earnings"
    assert conf_earn >= 0.65

    cat_div, _ = classifier.classify("Board declares special interim dividend of Rs 30 per share")
    assert cat_div == "dividend"

    mna_text = "Reliance completes acquisition of majority stake in retail venture"
    cat_mna, _ = classifier.classify(mna_text)
    assert cat_mna == "m&a"

    cat_reg, _ = classifier.classify("SEBI issues regulatory compliance mandate for brokers")
    assert cat_reg == "regulation"


def test_portfolio_exposure_aggregation_without_double_counting():
    """Verify portfolio exposure calculation excludes duplicate wire reprints."""
    now = datetime.now(UTC).isoformat()
    holdings = [
        {"symbol": "TCS", "weight": 0.60},
        {"symbol": "INFY", "weight": 0.40},
    ]

    art1 = NewsArticleCard(
        id="art-1",
        source_id="src-1",
        url="https://example.com/tcs-1",
        headline="TCS signs multi-year digital contract",
        publisher="Reuters",
        published_at=now,
        retrieved_at=now,
        is_duplicate=False,
        entities=[
            NewsEntityMatchSchema(
                symbol="TCS",
                company_name="TCS",
                match_type="exact_symbol",
                confidence=0.9,
                is_ambiguous=False,
                status="auto_matched",
            )
        ],
        signals=[
            NewsSignalSchema(
                symbol="TCS",
                is_market_wide=False,
                sentiment_score=0.40,
                sentiment_label="positive",
                sentiment_confidence=0.8,
                model_name="test",
                model_version="1.0",
                processing_time_ms=1.0,
                event_category="product",
                event_confidence=0.8,
            )
        ],
        affected_holdings=["TCS"],
        holding_exposure_weight_pct=60.0,
        explanation="Contract",
    )

    art2_duplicate = NewsArticleCard(
        id="art-2",
        source_id="src-2",
        url="https://example.com/tcs-2",
        headline="TCS signs multi-year digital contract (Wire)",
        publisher="Financial Express",
        published_at=now,
        retrieved_at=now,
        is_duplicate=True,  # Flagged duplicate!
        primary_article_id="art-1",
        entities=[
            NewsEntityMatchSchema(
                symbol="TCS",
                company_name="TCS",
                match_type="exact_symbol",
                confidence=0.9,
                is_ambiguous=False,
                status="auto_matched",
            )
        ],
        signals=[
            NewsSignalSchema(
                symbol="TCS",
                is_market_wide=False,
                sentiment_score=0.40,
                sentiment_label="positive",
                sentiment_confidence=0.8,
                model_name="test",
                model_version="1.0",
                processing_time_ms=1.0,
                event_category="product",
                event_confidence=0.8,
            )
        ],
        affected_holdings=["TCS"],
        holding_exposure_weight_pct=60.0,
        explanation="Duplicate",
    )

    aggregator = ExposureAggregator()
    port_sent, _, summaries = aggregator.aggregate_portfolio_exposure(
        holdings, [art1, art2_duplicate]
    )

    tcs_summary = next(s for s in summaries if s.symbol == "TCS")
    assert tcs_summary.article_count_24h == 1
    assert tcs_summary.article_count_7d == 1
    assert port_sent == 0.40


def test_api_news_routes():
    """Verify contract and responses for /api/v1/news/... and legacy news-signals."""
    client = TestClient(app)

    # 1. Provider status endpoint
    resp_st = client.get("/api/v1/news/provider-status")
    assert resp_st.status_code == 200
    st_data = resp_st.json()
    assert "provider_name" in st_data
    assert "provider_status" in st_data

    # 2. Backward-compatible /portfolio-analysis/news-signals
    payload = {
        "holdings": [
            {"symbol": "TCS", "quantity": 10, "buyPrice": 3500.0, "weight": 0.5},
            {"symbol": "INFY", "quantity": 20, "buyPrice": 1500.0, "weight": 0.5},
        ]
    }
    resp_sig = client.post("/api/v1/portfolio-analysis/news-signals", json=payload)
    assert resp_sig.status_code == 200
    sig_data = resp_sig.json()
    assert sig_data["contract_version"] == "v1-modular-draft"
    assert "stock_signals" in sig_data
    assert len(sig_data["stock_signals"]) == 2
