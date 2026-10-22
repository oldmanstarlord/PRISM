"""Firecrawl v2 client: discover first, scrape only new allowlisted articles."""

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from lxml import etree

from backend.app.core.config import Settings
from backend.app.news.publication_window import is_current_day
from backend.app.news.store import NewsStore


class ProviderError(RuntimeError):
    pass


def canonical_url(value: str, domains: list[str]) -> str | None:
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        if (
            parts.scheme != "https"
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
            or not any(host == d or host.endswith("." + d) for d in domains)
        ):
            return None
        query = urlencode(
            [
                (k, v)
                for k, v in parse_qsl(parts.query)
                if not k.lower().startswith("utm_") and k not in {"fbclid", "gclid"}
            ]
        )
        return urlunsplit(("https", host, parts.path.rstrip("/") or "/", query, ""))
    except (ValueError, AttributeError):
        return None


def publication_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            result = parsedate_to_datetime(value)
        if result.tzinfo is None:
            return None  # Do not invent the publisher's timezone.
        return result.astimezone(UTC).isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def clean_markdown(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return "\n".join(
        re.sub(r"^[#>*\s]+", "", line).strip() for line in text.splitlines() if line.strip()
    )[:60000]


class FirecrawlProvider:
    def __init__(self, config: Settings, store: NewsStore, client: httpx.Client) -> None:
        self.config, self.store, self.client = config, store, client

    def _post(self, endpoint: str, payload: dict[str, Any], credits: int) -> dict[str, Any]:
        key = self.config.firecrawl_api_key
        if not key or not key.get_secret_value().strip():
            raise ProviderError("Firecrawl API key is not configured")
        self.store.reserve(credits, self.config.news_daily_credit_budget)
        try:
            response = self.client.post(
                f"https://api.firecrawl.dev/v2/{endpoint}",
                json=payload,
                headers={"Authorization": f"Bearer {key.get_secret_value()}"},
                timeout=65,
            )
            if response.status_code in {401, 403}:
                raise ProviderError("Firecrawl rejected the API key or source access")
            if response.status_code == 402:
                raise ProviderError("Firecrawl account credits are exhausted")
            if response.status_code == 429:
                raise ProviderError("Firecrawl rate limit reached; try a later refresh")
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict) or body.get("success") is not True:
                raise ProviderError("Firecrawl could not retrieve this content")
            data = body.get("data")
            if not isinstance(data, dict):
                raise ProviderError("Firecrawl returned an unexpected response")
            return data
        except (httpx.HTTPError, ValueError) as exc:
            # Never forward provider bodies, request headers, or credentials to the browser.
            raise ProviderError(
                "Firecrawl request failed; cached articles are still available"
            ) from exc

    def discover(self) -> tuple[list[dict[str, Any]], list[str]]:
        items: list[dict[str, Any]] = []
        warnings: list[str] = []
        # Optional direct publisher RSS feeds avoid search credits. Fetch through Firecrawl
        # is unnecessary; only server-configured HTTPS publisher feed URLs are accepted.
        for feed in self.config.news_rss_urls[:10]:
            safe = canonical_url(feed, self.config.news_sources)
            if safe is None:
                warnings.append("An RSS feed was skipped because its domain is not allowed")
                continue
            try:
                response = self.client.get(safe, timeout=10, follow_redirects=False)
                response.raise_for_status()
                if len(response.content) > 2_000_000:
                    raise ValueError("Feed exceeds size limit")
                root = etree.fromstring(
                    response.content,
                    parser=etree.XMLParser(
                        resolve_entities=False,
                        no_network=True,
                        load_dtd=False,
                    ),
                )
                for item in root.findall(".//item")[:20]:
                    items.append(
                        {
                            "title": item.findtext("title", ""),
                            "url": item.findtext("link", ""),
                            "date": item.findtext("pubDate", ""),
                        }
                    )
            except (httpx.HTTPError, ValueError, etree.XMLSyntaxError):
                warnings.append("A configured RSS feed was unavailable")
        if not items:
            data = self._post(
                "search",
                {
                    "query": self.config.news_query,
                    "sources": [{"type": "news"}],
                    "limit": 10,
                    "includeDomains": self.config.news_sources,
                    "tbs": "qdr:d",
                },
                credits=2,
            )
            items = data.get("news", [])
            if not isinstance(items, list):
                raise ProviderError("Firecrawl returned an invalid news result list")
        candidates, seen = [], set()
        for item in items:
            if not isinstance(item, dict):
                continue
            published = publication_date(item.get("date"))
            # Missing discovery dates can still be verified from publisher metadata.
            if published and not is_current_day(published):
                continue
            url = canonical_url(str(item.get("url", "")), self.config.news_sources)
            if url and url not in seen:
                candidates.append({**item, "url": url})
                seen.add(url)
        return candidates, warnings

    def scrape(self, item: dict[str, Any]) -> dict[str, Any]:
        url = canonical_url(item["url"], self.config.news_sources)
        if url is None:
            raise ProviderError("Publisher URL is not allowed")
        data = self._post(
            "scrape",
            {
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "proxy": "basic",
                "maxAge": 3600000,
                "timeout": 45000,
            },
            credits=1,
        )
        meta = data.get("metadata") or {}
        if not isinstance(meta, dict):
            raise ProviderError("Article metadata is unavailable")
        final_url = canonical_url(
            str(meta.get("url") or meta.get("sourceURL") or url), self.config.news_sources
        )
        if not final_url or meta.get("error") or int(meta.get("statusCode", 200)) >= 400:
            raise ProviderError(
                "Publisher page is unavailable or redirected outside allowed sources"
            )
        language = str(meta.get("language") or "en").lower()
        if not language.startswith("en"):
            raise ProviderError("Only English articles are supported by this FinBERT model")
        text = clean_markdown(str(data.get("markdown") or ""))
        if len(text) < 200:
            raise ProviderError(
                "Article text is too short or unavailable; no sentiment was invented"
            )
        if re.search(
            r"(subscribe to (continue|read)|verify you are human|access denied)",
            text[:1000],
            flags=re.I,
        ):
            raise ProviderError("Publisher requires access; article skipped")
        title = str(item.get("title") or meta.get("title") or "Untitled article")[:500]
        published = publication_date(
            meta.get("article:published_time")
            or meta.get("publishedTime")
            or meta.get("datePublished")
            or item.get("date")
        )
        return {
            "url": final_url,
            "title": title,
            "text": text,
            "published_at": published,
            "publisher": urlsplit(final_url).hostname,
            "language": "en",
            "retrieved_at": datetime.now(UTC).isoformat(),
        }
