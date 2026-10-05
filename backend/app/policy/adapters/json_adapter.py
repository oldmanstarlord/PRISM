"""Explicit JSON file adapter for tests and controlled imports (Step 11)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from backend.app.policy.adapters.base import RawNewsItem


class JsonNewsAdapter:
    """Loads timestamped news items from a caller-supplied JSON file."""

    def __init__(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)

    def fetch_news(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawNewsItem]:
        if not self.file_path.exists():
            return []

        with open(self.file_path, encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return []

        items: list[RawNewsItem] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            pub_str = entry.get("published_at")
            if not pub_str:
                continue
            pub_dt = datetime.fromisoformat(pub_str)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=UTC)

            if since and pub_dt < since:
                continue

            item = RawNewsItem.create(
                headline=entry.get("headline", ""),
                url=entry.get("url", ""),
                source=entry.get("source", "UNKNOWN"),
                published_at=pub_dt,
            )
            items.append(item)

        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:limit] if limit else items
