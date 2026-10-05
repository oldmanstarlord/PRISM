"""Test news deduplication and canonical content hash computation (Step 11, D4, D6)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from backend.app.policy.adapters.base import RawNewsItem


def test_canonical_content_hash_determinism():
    """Verify identical headline, URL, and source produce identical canonical SHA-256 hash."""
    headline = "RBI increases risk weights on unsecured credit"
    url = "https://rbi.org.in/press/1"
    source = "RBI"
    dt = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)

    item1 = RawNewsItem.create(headline=headline, url=url, source=source, published_at=dt)
    item2 = RawNewsItem.create(
        headline=f"  {headline}  ", url=f" {url} ", source="rbi", published_at=dt
    )

    expected_str = f"RBI:{url}:{headline}"
    expected_hash = hashlib.sha256(expected_str.encode("utf-8")).hexdigest()

    assert item1.content_hash == expected_hash
    assert item2.content_hash == expected_hash
    assert item1.content_hash == item2.content_hash


def test_dedup_suppresses_duplicate_items():
    """Verify deduplication set correctly identifies already ingested news items."""
    seen_hashes: set[str] = set()
    dt = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)

    item = RawNewsItem.create(
        headline="SEBI mandates enhanced disclosure for derivative positions",
        url="https://sebi.gov.in/pr/2",
        source="SEBI",
        published_at=dt,
    )

    # First encounter
    assert item.content_hash not in seen_hashes
    seen_hashes.add(item.content_hash)

    # Second encounter
    is_duplicate = item.content_hash in seen_hashes
    assert is_duplicate is True
