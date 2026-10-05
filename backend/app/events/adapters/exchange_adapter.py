"""Exchange announcement adapter for NSE/BSE corporate announcements with fallback (FR-D9)."""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from backend.app.events.adapters.base import AnnouncementAdapter, RawAnnouncement
from backend.app.events.adapters.json_adapter import JsonAnnouncementAdapter

logger = logging.getLogger(__name__)


class ExchangeAnnouncementAdapter(AnnouncementAdapter):
    """Fetches corporate announcements from Indian stock exchanges with fallback to fixtures."""

    def __init__(self, use_fallback: bool = True) -> None:
        self.use_fallback = use_fallback
        self.fallback_adapter = JsonAnnouncementAdapter()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def fetch_announcements(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawAnnouncement]:
        """Fetch live announcements from exchange feed, with graceful fallback to fixtures."""
        try:
            # Simulated live retrieval with short timeout
            url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
            resp = self.session.get(url, timeout=4.0)
            announcements: list[RawAnnouncement] = []
            if resp.status_code == 200:
                payload = resp.json()
                if isinstance(payload, dict):
                    for item in payload.get("data", []):
                        if not isinstance(item, dict):
                            continue
                        pub_str = item.get("an_dt")
                        if not pub_str:
                            continue
                        pub_dt = datetime.fromisoformat(pub_str)
                        if since and pub_dt < since:
                            continue
                        announcements.append(
                            RawAnnouncement(
                                symbol=item.get("symbol", "").strip().upper(),
                                isin=item.get("isin"),
                                company_name=item.get("sm_name", ""),
                                headline=item.get("desc", "").strip(),
                                body=item.get("attchmntText"),
                                source_category=item.get("sub", "General Compliance"),
                                published_at=pub_dt,
                                source_doc_id=f"NSE_{item.get('seq_id', '')}",
                                url=item.get("attmntFile"),
                            )
                        )
                if announcements:
                    return announcements[:limit] if limit else announcements
        except Exception as exc:
            logger.info("Live exchange feed unavailable (%s); falling back to fixtures", exc)

        if self.use_fallback:
            return self.fallback_adapter.fetch_announcements(since=since, limit=limit)
        return []
