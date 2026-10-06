"""Unit and regression tests for News Impact service (Step E4)."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from backend.app.db.models import NewsImpact, NewsItem
from backend.app.news_impact.service import calculate_news_impact


def test_idempotent_news_impact_reuses_completed_run() -> None:
    session = MagicMock()
    news_id = uuid4()
    news = MagicMock(spec=NewsItem)
    news.id = news_id
    news.source = "RBI"
    news.content_hash = "mock_hash_123"
    news.published_at = MagicMock()
    news.ingested_at = MagicMock()

    # Mock load config
    mock_config = {
        "live_source_map": {"RBI": "news_rbi_rss"},
        "unreviewed_rule_confidence_penalty": 0.25,
        "base_confidence": {"rule": 0.85, "direct": 0.95, "macro": 0.70, "spillover": 0.65},
        "maximum_stocks_per_item": 10,
        "direct_default_severity": 5.0,
        "spillover_min_r_squared": 0.25,
        "regression_window": 120,
        "recency_half_life_days": 30.0,
        "exposure_bands": {"medium_min": 0.35, "high_min": 0.65},
        "path_weights": {"direct": 1.0, "rule": 0.85, "macro": 0.7, "spillover": 0.6},
        "minimum_confidence_to_display": 0.40,
    }

    # First call: returns existing run
    existing_run = MagicMock(spec=NewsImpact)
    existing_run.id = uuid4()
    existing_run.status = "completed"

    # Set up session scalar return values
    # 1. Config loading
    # 2. _source_is_live check
    # 3. existing run query
    session.scalar.side_effect = [
        # load_news_impact_config
        MagicMock(configuration=mock_config, configuration_hash="cfg_hash_abc"),
        # existing run
        existing_run,
    ]
    session.get.return_value = MagicMock(status="live", last_success_at=MagicMock())
    session.execute.return_value.all.return_value = []
    session.scalars.return_value.all.return_value = []

    run, was_reused = calculate_news_impact(session, news)
    assert was_reused is True
    assert run == existing_run
    # Session add should not have been called for a new run
    session.add.assert_not_called()
