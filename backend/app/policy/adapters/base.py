"""Base adapter protocol and data models for news and regulatory feeds (Step 11, D4)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RawNewsItem:
    headline: str
    url: str
    source: str
    published_at: datetime
    content_hash: str

    @classmethod
    def create(
        cls,
        headline: str,
        url: str,
        source: str,
        published_at: datetime,
    ) -> RawNewsItem:
        clean_head = headline.strip()
        clean_url = url.strip()
        clean_src = source.strip().upper()
        # Canonical hash: SHA256 of source:url:headline
        hash_str = f"{clean_src}:{clean_url}:{clean_head}"
        content_hash = hashlib.sha256(hash_str.encode("utf-8")).hexdigest()
        return cls(
            headline=clean_head,
            url=clean_url,
            source=clean_src,
            published_at=published_at,
            content_hash=content_hash,
        )


class NewsAdapter(Protocol):
    """Protocol for news and regulatory press release adapters (FR-D9)."""

    def fetch_news(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawNewsItem]:
        """Fetch raw timestamped news items point-in-time."""
        ...
