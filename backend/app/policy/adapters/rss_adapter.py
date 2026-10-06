"""Official RSS/Atom adapter that stores metadata only, never article bodies."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import requests

from backend.app.policy.adapters.base import RawNewsItem

logger = logging.getLogger(__name__)

OFFICIAL_FEEDS: tuple[dict[str, str], ...] = (
    {
        "source": "RBI",
        "source_key": "news_rbi_rss",
        "name": "Reserve Bank of India Press Releases",
        "url": "https://rbi.org.in/pressreleases_rss.xml",
        "terms_url": "https://www.rbi.org.in/Scripts/rss.aspx",
    },
    {
        "source": "SEBI",
        "source_key": "news_sebi_rss",
        "name": "Securities and Exchange Board of India RSS",
        "url": "https://www.sebi.gov.in/sebirss.xml",
        "terms_url": "https://www.sebi.gov.in/rss.html",
    },
)


def _text(element: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _published_at(value: str) -> datetime:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.strptime(value, "%d %b, %Y %z")
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_items(content: bytes, source: str) -> list[RawNewsItem]:
    root = ET.fromstring(content)
    entries = root.findall(".//item")
    if not entries:
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    output: list[RawNewsItem] = []
    for entry in entries:
        headline = _text(entry, ("title", "{http://www.w3.org/2005/Atom}title"))
        url = _text(entry, ("link",))
        if not url:
            atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
            if atom_link is not None:
                url = atom_link.attrib.get("href", "").strip()
        timestamp = _text(
            entry,
            (
                "pubDate",
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
            ),
        )
        if not headline or not url or not timestamp:
            continue
        try:
            published_at = _published_at(timestamp)
        except ValueError:
            logger.warning("RSS feed %s contains an unreadable item timestamp", source)
            continue
        output.append(
            RawNewsItem.create(
                headline=headline,
                url=url,
                source=source,
                published_at=published_at,
            )
        )
    return output


class RssNewsAdapter:
    """Fetch only the verified feed allowlist unless explicitly injected in a test."""

    def __init__(self, timeout_seconds: float = 10.0, rss_url: str | None = None) -> None:
        self.timeout = timeout_seconds
        self.rss_url = rss_url
        self.feed_results: list[dict[str, str | int | None]] = []
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "PRISM-Risk-System/1.0 (official-feed metadata reader)"}
        )

    def fetch_news(
        self,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[RawNewsItem]:
        feeds = (
            (
                {
                    "source": "CUSTOM",
                    "source_key": "custom_test_feed",
                    "name": "Injected feed",
                    "url": self.rss_url,
                    "terms_url": "",
                },
            )
            if self.rss_url
            else OFFICIAL_FEEDS
        )
        items: list[RawNewsItem] = []
        self.feed_results = []
        successful_feeds = 0
        for feed in feeds:
            source = feed["source"]
            try:
                response = self.session.get(feed["url"], timeout=self.timeout)
                response.raise_for_status()
                parsed_items = _parse_items(response.content, source)
                if not parsed_items:
                    raise ValueError("feed returned no complete timestamped items")
                successful_feeds += 1
                visible_items = [
                    item for item in parsed_items if since is None or item.published_at >= since
                ]
                items.extend(visible_items)
                newest = max(item.published_at for item in parsed_items)
                self.feed_results.append(
                    {
                        "source": source,
                        "source_key": feed["source_key"],
                        "status": "success",
                        "item_count": len(visible_items),
                        "newest_published_at": newest.isoformat(),
                    }
                )
            except (requests.RequestException, ET.ParseError, ValueError) as exc:
                self.feed_results.append(
                    {
                        "source": source,
                        "source_key": feed["source_key"],
                        "status": "failed",
                        "item_count": 0,
                        "newest_published_at": None,
                    }
                )
                logger.error("RSS feed %s failed: %s", source, exc)
        if successful_feeds == 0:
            raise RuntimeError("every configured RSS feed failed; no news rows were written")
        items.sort(key=lambda item: item.published_at, reverse=True)
        return items[:limit] if limit is not None else items
