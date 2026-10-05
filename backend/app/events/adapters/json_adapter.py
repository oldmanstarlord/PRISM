"""File-based JSON announcement adapter for reproducible testing and fixture ingestion (D4)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from backend.app.events.adapters.base import AnnouncementAdapter, RawAnnouncement


class JsonAnnouncementAdapter(AnnouncementAdapter):
    """Loads curated exchange announcements from a JSON file fixture."""

    def __init__(self, file_path: Path | str | None = None) -> None:
        if file_path is None:
            self.file_path = (
                Path(__file__).resolve().parents[4]
                / "data"
                / "announcements"
                / "announcements.json"
            )
        else:
            self.file_path = Path(file_path)

    def fetch_announcements(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawAnnouncement]:
        if not self.file_path.exists():
            return []

        with open(self.file_path, encoding="utf-8") as f:
            records = json.load(f)

        results: list[RawAnnouncement] = []
        for r in records:
            published_at = datetime.fromisoformat(r["published_at"])
            if since and published_at < since:
                continue

            results.append(
                RawAnnouncement(
                    symbol=r["symbol"].strip().upper(),
                    isin=r.get("isin"),
                    company_name=r.get("company_name", r["symbol"]),
                    headline=r["headline"].strip(),
                    body=r.get("body"),
                    source_category=r["source_category"].strip(),
                    published_at=published_at,
                    source_doc_id=r["source_doc_id"].strip(),
                    url=r.get("url"),
                )
            )

        if limit:
            results = results[:limit]
        return results
