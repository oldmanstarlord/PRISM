"""Base protocol and data transfer structures for company announcement adapters (D4, FR-D9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class RawAnnouncement:
    """Raw company announcement extracted from an exchange feed or document archive."""

    symbol: str
    company_name: str
    headline: str
    source_category: str
    published_at: datetime
    source_doc_id: str
    isin: str | None = None
    body: str | None = None
    url: str | None = None


class AnnouncementAdapter(Protocol):
    """Protocol for exchange and filing announcement ingestion sources."""

    def fetch_announcements(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawAnnouncement]:
        """Fetch announcement records published since cutoff."""
        ...
