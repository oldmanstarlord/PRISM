"""Official RSS/Atom feed adapter for regulatory agencies and ministries (Step 11)."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests

from backend.app.policy.adapters.base import RawNewsItem

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
]


class RssNewsAdapter:
    """Fetches public announcements and press releases from official regulatory RSS feeds."""

    def __init__(
        self,
        timeout_seconds: float = 10.0,
        rss_url: str | None = None,
    ) -> None:
        self.timeout = timeout_seconds
        self.rss_url = rss_url
        self.feed_results: list[dict[str, str | int | None]] = []
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

        successful_feeds = 0
        self.feed_results = []
        for feed in feeds:
            source = feed["source"]
            url = feed["url"]
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
                feed_items: list[RawNewsItem] = []
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

                        if not headline or not item_url or not pub_str:
                            continue

                        # Parse pubDate (RFC 822 format or ISO)
                        try:
                            pub_dt = parsedate_to_datetime(pub_str)
                        except (TypeError, ValueError, OverflowError):
                            try:
                                pub_dt = datetime.fromisoformat(pub_str)
                            except ValueError:
                                try:
                                    pub_dt = datetime.strptime(pub_str, "%d %b, %Y %z")
                                except ValueError:
                                    logger.warning(
                                        "RSS feed %s item has invalid date; skipping", source
                                    )
                                    continue

                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=UTC)

                        if since and pub_dt < since:
                            continue

                        feed_items.append(
                            RawNewsItem.create(
                                headline=headline,
                                url=item_url,
                                source=source,
                                published_at=pub_dt,
                            )
                        )
                successful_feeds += 1
                items.extend(feed_items)
                newest = max((item.published_at for item in feed_items), default=None)
                self.feed_results.append(
                    {
                        "source": source,
                        "status": "success",
                        "item_count": len(feed_items),
                        "newest_published_at": newest.isoformat() if newest else None,
                    }
                )
                logger.info(
                    "RSS feed %s succeeded: %d items; newest=%s",
                    source,
                    len(feed_items),
                    newest.isoformat() if newest else "none",
                )
            except Exception as exc:
                self.feed_results.append(
                    {
                        "source": source,
                        "status": "failed",
                        "item_count": 0,
                        "newest_published_at": None,
                    }
                )
                logger.error("RSS feed %s failed: %s", source, exc)

        if successful_feeds == 0:
            raise RuntimeError("Every configured RSS feed failed; no news rows were written")

        if items:
            items.sort(key=lambda x: x.published_at, reverse=True)
            return items[:limit] if limit else items

        return []
