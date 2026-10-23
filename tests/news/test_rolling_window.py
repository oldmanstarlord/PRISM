from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import httpx
import pytest

from backend.app.core.config import Settings
from backend.app.news import collection
from backend.app.news.collection import NewsService
from backend.app.news.exposure_aggregator import ExposureAggregator
from backend.app.news.provider import FirecrawlProvider
from backend.app.news.publication_window import is_in_news_window
from backend.app.news.relevance import select_active_articles
from backend.app.news.schemas import NewsArticleCard, NewsEntityMatchSchema, NewsSignalSchema
from backend.app.news.store import NewsStore

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def article(url, days, title="TCS buys Alpha Labs in acquisition", **extra):
    return {
        "url": "https://example.com/" + url,
        "title": title,
        "excerpt": title,
        "published_at": (NOW - timedelta(days=days)).isoformat(),
        "retrieved_at": NOW.isoformat(),
        "content_hash": url,
        "companies": {"TCS": {}},
        "sentiment": {"model": "test"},
        **extra,
    }


@pytest.mark.parametrize(
    "offset,expected",
    [
        (timedelta(days=7), True),
        (timedelta(days=7, microseconds=1), False),
        (timedelta(days=1), True),
        (timedelta(0), True),
        (timedelta(seconds=-1), False),
    ],
)
def test_rolling_168_hour_publication_boundary(offset, expected):
    assert is_in_news_window((NOW - offset).isoformat(), NOW) is expected


@pytest.mark.parametrize("value", [None, "garbage", "2026-10-22T12:00:00"])
def test_invalid_dates_never_become_fresh(value):
    assert not is_in_news_window(value, NOW)


def test_retention_needs_recent_evidence_same_company_and_same_topic():
    old = article("old", 40)
    recent = article("followup", 1, "TCS Alpha Labs acquisition awaiting clearance")
    unrelated = article("unrelated", 10, "TCS buys textile business in acquisition")
    other_company = article("other", 10, companies={"INFY": {}})
    routine = article("routine", 10, "TCS stock trading update")
    duplicate = article("duplicate", 10, duplicate_of=old["url"])
    active = select_active_articles(
        [old, recent, unrelated, other_company, routine, duplicate], NOW
    )
    assert {a["url"] for a in active} == {old["url"], recent["url"]}
    context = next(a for a in active if a["is_retained_context"])
    assert context["related_article_url"] == recent["url"]
    assert context["relevance_until"] == (NOW + timedelta(days=6)).isoformat()
    assert select_active_articles([old, recent], NOW + timedelta(days=8)) == []


def test_archive_cleanup_preserves_supported_context_beyond_thirty_days(tmp_path):
    shift = datetime.now(UTC) - NOW
    articles = [
        article("old", 40),
        article("followup", 1),
        article("unrelated", 40, "Unrelated stock price movement"),
    ]
    for a in articles:
        a["published_at"] = (datetime.fromisoformat(a["published_at"]) + shift).isoformat()
        a["retrieved_at"] = a["published_at"]
    store = NewsStore(tmp_path / "news.sqlite3")
    for a in articles:
        store.save(a)
    store.prune()
    assert {a["url"] for a in store.articles(days=None)} == {a["url"] for a in articles[:2]}


def test_discovery_searches_week_and_accepts_web_backfill(tmp_path):
    config = Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost/prism",
        firecrawl_api_key="test-key",
        news_sources=["example.com"],
    )
    now = datetime.now(UTC)

    def respond(request):
        import json

        payload = json.loads(request.content)
        assert payload["tbs"] == "sbd:1,qdr:w"
        assert payload["sources"] == [{"type": "news"}, {"type": "web"}]
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "news": [],
                    "web": [
                        {
                            "url": "https://example.com/yesterday",
                            "date": (now - timedelta(days=1)).isoformat(),
                        },
                        {
                            "url": "https://example.com/expired",
                            "date": (now - timedelta(days=8)).isoformat(),
                        },
                        {"url": "https://example.com/metadata-needed"},
                    ],
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        candidates, warnings = FirecrawlProvider(
            config, NewsStore(tmp_path / "news.db"), client
        ).discover()
    assert not warnings
    assert {a["url"] for a in candidates} == {
        "https://example.com/yesterday",
        "https://example.com/metadata-needed",
    }


def test_collection_analyzes_previous_days_and_survives_restart(tmp_path, monkeypatch):
    config = Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost/prism",
        firecrawl_api_key="test-key",
        news_cache_path=tmp_path / "news.db",
    )
    service = NewsService(config)
    service.analyzer = Mock()
    service.analyzer.downloaded.return_value = True
    service.analyzer.analyze.return_value = {"model": "test", "score": 0.8}
    monkeypatch.setattr(
        collection, "load_companies", lambda _: [("TCS", "Tata Consultancy Services Limited")]
    )
    monkeypatch.setattr(
        FirecrawlProvider, "discover", lambda _: ([{"url": "https://example.com/a"}], [])
    )
    monkeypatch.setattr(
        FirecrawlProvider,
        "scrape",
        lambda _, item: {
            **item,
            "title": "TCS earnings",
            "text": "TCS reports growing revenue.",
            "published_at": (datetime.now(UTC) - timedelta(days=3)).isoformat(),
            "retrieved_at": datetime.now(UTC).isoformat(),
        },
    )
    service.collect(service.prepare())
    assert service.analyzer.analyze.call_count == 2
    assert len(NewsService(config).feed()["articles"]) == 1


def test_seven_day_scores_include_yesterday_but_exclude_retained_context():
    now = datetime.now(UTC)

    def card(key, days, score, **extra):
        return NewsArticleCard(
            id=key,
            source_id=key,
            headline=key,
            publisher="Example",
            url="https://example.com/" + key,
            published_at=(now - timedelta(days=days)).isoformat(),
            retrieved_at=now.isoformat(),
            entities=[
                NewsEntityMatchSchema(
                    symbol="TCS", company_name="TCS", match_type="company_name", confidence=1
                )
            ],
            signals=[
                NewsSignalSchema(
                    symbol="TCS",
                    sentiment_score=score,
                    sentiment_label="positive",
                    sentiment_confidence=1,
                    model_name="test",
                    model_version="test",
                    processing_time_ms=0,
                    event_category="m&a",
                    event_confidence=1,
                )
            ],
            **extra,
        )

    score, _, summaries = ExposureAggregator().aggregate_portfolio_exposure(
        [{"symbol": "TCS", "weight": 1.0}],
        [
            card("today", 0.1, 0.8),
            card("yesterday", 2, 0.4),
            card(
                "context",
                12,
                -1,
                is_retained_context=True,
                relevance_until=(now + timedelta(days=2)).isoformat(),
            ),
            card("expired", 8, -1),
            card("future", -1, -1),
        ],
    )
    assert score == 0.6
    assert summaries[0].article_count_7d == 2
    assert summaries[0].article_count_24h == 1
    assert summaries[0].retained_context_count == 1
