"""Coverage contract: no external dataset may silently disappear from the registry."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data_sources.service import registry_freshness_status, source_policy
from backend.app.db.models import DataSource, MacroSeriesDefinition


def test_every_required_dataset_and_macro_series_is_registered(session: Session) -> None:
    sources = session.scalars(select(DataSource)).all()
    datasets = {row.dataset for row in sources}
    assert {
        "prices",
        "benchmark",
        "fundamentals",
        "shareholding",
        "shares_outstanding",
        "insider_trades",
        "announcements",
        "news_policy",
    } <= datasets

    macro_keys = set(session.scalars(select(MacroSeriesDefinition.series_key)).all())
    assert {f"macro:{key}" for key in macro_keys} <= datasets

    policies = source_policy(session)
    assert {row.source_key for row in sources} == set(policies)
    assert all(row.status in {"live", "manual", "tbd", "disabled"} for row in sources)


def test_registry_freshness_boundaries_missing_and_no_lookahead() -> None:
    now = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    last = now - timedelta(minutes=90)
    assert registry_freshness_status(now, last, 60, 30) == "fresh"
    assert registry_freshness_status(now + timedelta(seconds=1), last, 60, 30) == "stale"
    assert registry_freshness_status(now, None, 60, 30) == "missing"
    with pytest.raises(ValueError, match="after evaluation"):
        registry_freshness_status(now, now + timedelta(seconds=1), 60, 30)
