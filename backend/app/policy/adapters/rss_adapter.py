"""Official RSS/Atom feed adapter for regulatory agencies and ministries (Step 11)."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests

from backend.app.policy.adapters.base import RawNewsItem
from backend.app.policy.adapters.json_adapter import JsonNewsAdapter

logger = logging.getLogger(__name__)

OFFICIAL_FEEDS: list[dict[str, str]] = [
    {
        "source": "RBI",
        "name": "Reserve Bank of India Press Releases",
        "url": "https://rbi.org.in/pressreleases_rss.xml",
        "terms": (
            "Public regulatory releases published by Reserve Bank of India "
            "for public dissemination."
        ),
    },
    {
        "source": "SEBI",
        "name": "Securities and Exchange Board of India",
        "url": "https://www.sebi.gov.in/sebirss.xml",
        "terms": "Public regulatory orders and circulars published by SEBI.",
    },
    {
        "source": "PIB",
        "name": "Press Information Bureau - Ministry of Finance",
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1",
        "terms": "Government of India open data public press releases.",
    },
]


class RssNewsAdapter:
    """Fetches public announcements and press releases from official regulatory RSS feeds."""

    def __init__(
        self,
        use_fallback: bool = True,
        timeout_seconds: float = 3.0,
        rss_url: str | None = None,
    ) -> None:
        self.use_fallback = use_fallback
        self.timeout = timeout_seconds
        self.fallback_adapter = JsonNewsAdapter()
        self.rss_url = rss_url
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "PRISM-Risk-System/1.0 (+https://prism.local; research/regulatory-feed)"}
        )

    def fetch_news(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawNewsItem]:
        items: list[RawNewsItem] = []
        feeds = (
            [{"source": "CUSTOM", "name": "Custom", "url": self.rss_url, "terms": "Custom"}]
            if self.rss_url
            else OFFICIAL_FEEDS
        )

        for feed in feeds:
            source = feed["source"]
            url = feed["url"]
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.content)
                    # Standard RSS 2.0 channel/item structure
                    for item_elem in root.findall(".//item"):
                        title_elem = item_elem.find("title")
                        link_elem = item_elem.find("link")
                        pub_elem = item_elem.find("pubDate")

                        headline = (
                            title_elem.text.strip()
                            if title_elem is not None and title_elem.text
                            else ""
                        )
                        item_url = (
                            link_elem.text.strip()
                            if link_elem is not None and link_elem.text
                            else ""
                        )
                        pub_str = (
                            pub_elem.text.strip()
                            if pub_elem is not None and pub_elem.text
                            else ""
                        )

                        if not headline:
                            continue

                        # Parse pubDate (RFC 822 format or ISO)
                        pub_dt: datetime
                        if pub_str:
                            try:
                                pub_dt = parsedate_to_datetime(pub_str)
                            except Exception:
                                pub_dt = datetime.now(UTC)
                        else:
                            pub_dt = datetime.now(UTC)

                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=UTC)

                        if since and pub_dt < since:
                            continue

                        items.append(
                            RawNewsItem.create(
                                headline=headline,
                                url=item_url or f"{url}#{hash(headline)}",
                                source=source,
                                published_at=pub_dt,
                            )
                        )
            except Exception as exc:
                logger.info("RSS feed %s unavailable (%s); using resilient fallback", source, exc)

        if items:
            items.sort(key=lambda x: x.published_at, reverse=True)
            return items[:limit] if limit else items

        if self.use_fallback:
            return self.fallback_adapter.fetch_news(since=since, limit=limit)

        return []
