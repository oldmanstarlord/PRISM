from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.news import collection, collection_router
from backend.app.news.collection import NewsService, company_passages, duplicate
from backend.app.news.provider import (
    FirecrawlProvider,
    ProviderError,
    canonical_url,
    publication_date,
)
from backend.app.news.sentiment import MODEL_VERSION
from backend.app.news.store import NewsStore, RefreshBlocked


@pytest.fixture
def config(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost/prism",
        firecrawl_api_key="test-only-key",
        news_cache_path=tmp_path / "news.sqlite3",
        news_sources=["example.com"],
        news_refresh_minutes=5,
    )


def score() -> dict:
    return {
        "label": "positive",
        "score": 0.85,
        "confidence": 0.9,
        "probabilities": {"positive": 0.9, "negative": 0.05, "neutral": 0.05},
        "model": MODEL_VERSION,
        "chunks_analyzed": 1,
        "truncated": False,
    }


def test_url_policy_rejects_unsafe_destinations_and_preserves_meaningful_query():
    domains = ["example.com"]
    assert canonical_url("https://news.example.com/a?utm_source=x&id=2#top", domains) == (
        "https://news.example.com/a?id=2"
    )
    for url in [
        "http://example.com/a",
        "https://example.com.evil.com/a",
        "https://localhost/a",
        "https://user:pass@example.com/a",
        "javascript:alert(1)",
        "https://example.com:9000/a",
    ]:
        assert canonical_url(url, domains) is None


def test_dates_do_not_invent_publication_time():
    assert publication_date("3 hours ago") is None
    assert publication_date("2026-10-21T12:00:00") is None
    assert publication_date("2026-10-21T12:00:00+05:30") == "2026-10-21T06:30:00+00:00"


def test_budget_and_refresh_lock_persist_across_instances(config):
    first = NewsStore(config.news_cache_path)
    second = NewsStore(config.news_cache_path)
    first.reserve(2, 3)
    second.reserve(1, 3)
    with pytest.raises(RefreshBlocked, match="budget"):
        first.reserve(1, 3)
    token = first.begin(5)
    with pytest.raises(RefreshBlocked, match="already running"):
        second.begin(5)
    first.finish(token, None, [], 0)
    with pytest.raises(RefreshBlocked, match="every 5"):
        second.begin(5)
    assert second.used_today() == 3


@pytest.mark.parametrize(
    "status,message",
    [(401, "API key"), (402, "exhausted"), (429, "rate limit"), (500, "request failed")],
)
def test_provider_errors_are_actionable_and_redacted(config, status, message):
    store = NewsStore(config.news_cache_path)
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"error": "secret provider internals"})
        )
    ) as client:
        with pytest.raises(ProviderError, match=message) as error:
            FirecrawlProvider(config, store, client).discover()
        assert "secret" not in str(error.value)
    assert store.used_today() == 2


def test_scrape_rejects_paywall_and_does_not_analyze_missing_text(config):
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"success": True, "data": {"markdown": "Subscribe to continue " * 30}}
            )
        )
    ) as client:
        with pytest.raises(ProviderError, match="requires access"):
            FirecrawlProvider(config, NewsStore(config.news_cache_path), client).scrape(
                {"url": "https://example.com/story", "title": "Markets"}
            )


def test_entity_sentiment_uses_company_passages_and_avoids_ambiguous_oil():
    text = "TCS reported record profits.\nInfosys reported a loss.\nOIL prices surged globally."
    matches = company_passages(
        text,
        [
            ("TCS", "Tata Consultancy Services Limited"),
            ("INFY", "Infosys Limited"),
            ("OIL", "Oil India Limited"),
        ],
    )
    assert "loss" not in matches["TCS"]
    assert "profits" not in matches["INFY"]
    assert "OIL" not in matches


def test_changed_article_on_same_url_is_reprocessed():
    old = {"url": "https://example.com/a", "title": "Company results", "content_hash": "old"}
    assert not duplicate({**old, "content_hash": "new"}, [old])
    assert duplicate({**old, "url": "https://example.com/syndicated"}, [old])


def test_collection_runs_once_caches_inference_and_deduplicates(config, monkeypatch):
    service = NewsService(config)
    analyzer = Mock()
    analyzer.downloaded.return_value = True
    analyzer.analyze.return_value = score()
    service.analyzer = analyzer
    monkeypatch.setattr(
        collection, "load_companies", lambda config: [("TCS", "Tata Consultancy Services Limited")]
    )
    calls = []
    published = datetime.now(UTC).isoformat()

    def respond(request):
        calls.append(request.url.path)
        if request.url.path.endswith("search"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "news": [
                            {
                                "url": "https://example.com/a",
                                "title": "TCS reports record quarterly earnings",
                            },
                            {
                                "url": "https://example.com/b",
                                "title": "TCS reports record quarterly earnings",
                            },
                        ]
                    },
                },
            )
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "markdown": "TCS reported record profits and growing revenue. " * 10,
                    "metadata": {"article:published_time": published},
                },
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(collection.httpx, "Client", lambda: client)
    service.collect(service.prepare())
    feed = service.feed()
    assert len(feed["articles"]) == 1
    assert feed["articles"][0]["companies"]["TCS"]["model"] == MODEL_VERSION
    assert analyzer.analyze.call_count == 2  # Article and company passage, never syndicated copy.
    assert service.store.recent("https://example.com/b", MODEL_VERSION)
    assert feed["status"]["credits_reserved_today"] == 4
    assert len(calls) == 3
    # A new process still serves cached scores without calling Firecrawl or FinBERT.
    monkeypatch.undo()
    reopened = NewsService(config)
    assert len(reopened.feed()["articles"]) == 1
    assert "text" not in reopened.feed()["articles"][0]


def test_failures_preserve_cached_news(config, monkeypatch):
    service = NewsService(config)
    now = datetime.now(UTC).isoformat()
    service.store.save(
        {
            "url": "https://example.com/a",
            "content_hash": "old",
            "title": "Old",
            "published_at": now,
            "retrieved_at": now,
            "companies": {},
            "sentiment": score(),
        }
    )
    service.analyzer = Mock()
    service.analyzer.downloaded.return_value = True
    monkeypatch.setattr(collection, "load_companies", lambda config: [])
    monkeypatch.setattr(
        FirecrawlProvider, "discover", Mock(side_effect=ProviderError("provider offline"))
    )
    service.collect(service.prepare())
    assert len(service.feed()["articles"]) == 1
    assert service.status()["error"] == "provider offline"
    assert not service.status()["running"]


def test_stale_stories_and_duplicates_excluded_from_feed(config):
    service = NewsService(config)
    now = datetime.now(UTC).isoformat()
    old = (datetime.now(UTC) - timedelta(days=20)).isoformat()
    for url, extra in [("a", {"published_at": old}), ("b", {"duplicate_of": "a"})]:
        service.store.save(
            {
                "url": url,
                "content_hash": url,
                "retrieved_at": now,
                "sentiment": score(),
                "companies": {},
                **extra,
            }
        )
    assert service.feed()["articles"] == []


def test_refresh_requires_auth_outside_loopback_and_missing_key_is_explicit(config, monkeypatch):
    from backend.app.main import app

    config.firecrawl_api_key = None
    monkeypatch.setattr(collection_router, "get_news_service", lambda: NewsService(config))
    client = TestClient(app)
    assert client.post("/api/v1/news/refresh", json={}).status_code == 401
    app.dependency_overrides[collection_router.authorize_refresh] = lambda: None
    try:
        response = client.post("/api/v1/news/refresh", json={})
        assert response.status_code == 503
        assert "PRISM_FIRECRAWL_API_KEY" in response.json()["detail"]
        assert client.get("/api/v1/news").json()["articles"] == []
    finally:
        app.dependency_overrides.pop(collection_router.authorize_refresh, None)
