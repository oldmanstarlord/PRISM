"""Placeholder for a future licensed or official exchange announcement feed."""

from __future__ import annotations

from datetime import datetime

from backend.app.events.adapters.base import AnnouncementAdapter, RawAnnouncement


class ExchangeAnnouncementAdapter(AnnouncementAdapter):
    """Disabled until an approved official feed or licensed source is configured."""

    def fetch_announcements(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawAnnouncement]:
        """Refuse ingestion until the TBD production source has been approved."""
        del since, limit
        raise RuntimeError(
            "Corporate-announcement live source is TBD; provide an explicit real export file"
        )
