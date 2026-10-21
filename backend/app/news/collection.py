"""Shared collection, deduplication, entity matching and sentiment orchestration."""

import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.db.models import Security, SecurityAlias
from backend.app.news.entity_matcher import AMBIGUOUS_TICKER_COLLISIONS, NIFTY_CORE_ENTITIES
from backend.app.news.provider import FirecrawlProvider, ProviderError
from backend.app.news.sentiment import MODEL_VERSION, ModelUnavailable, SentimentAnalyzer
from backend.app.news.store import NewsStore, RefreshBlocked

logger = logging.getLogger(__name__)


def fingerprint(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text.lower()).strip().encode()).hexdigest()


def duplicate(article: dict[str, Any], existing: list[dict[str, Any]]) -> bool:
    title = re.sub(r"\W+", " ", article["title"].lower()).strip()
    for old in existing:
        if old["url"] == article["url"]:
            # A changed article on the same URL must be reanalyzed.
            return bool(old["content_hash"] == article["content_hash"])
        other = re.sub(r"\W+", " ", old["title"].lower()).strip()
        if old["content_hash"] == article["content_hash"] or (
            len(title) >= 30 and SequenceMatcher(None, title, other).ratio() > 0.94
        ):
            return True
    return False


def company_passages(text: str, companies: list[tuple[str, str]]) -> dict[str, str]:
    passages = re.split(r"\n+|(?<=[.!?])\s+", text)
    matches: dict[str, str] = {}
    for symbol, name in companies:
        name = re.sub(r"\s+(Limited|Ltd\.?)$", "", name, flags=re.I).strip()
        if len(name) < 4:
            continue
        name_pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.I)
        symbol_pattern = re.compile(r"(?<!\w)" + re.escape(symbol) + r"(?!\w)")
        # Very short symbols are ambiguous English words; match the company name instead.
        aliases: list[str] = next(
            (e["aliases"] for e in NIFTY_CORE_ENTITIES if e["symbol"] == symbol), []
        )
        alias_patterns = [
            re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", re.I)
            for alias in aliases
            if len(alias) >= 4 and alias.upper() != symbol
        ]
        relevant = [
            p
            for p in passages
            if name_pattern.search(p)
            or any(pattern.search(p) for pattern in alias_patterns)
            or (
                len(symbol) >= 3
                and symbol not in AMBIGUOUS_TICKER_COLLISIONS
                and symbol_pattern.search(p)
            )
        ]
        if relevant:
            matches[symbol] = "\n".join(relevant)
    return matches


def load_companies(config: Settings) -> list[tuple[str, str]]:
    engine = create_engine(config.database_url, connect_args={"connect_timeout": 3})
    try:
        with Session(engine) as session:
            return [
                (str(symbol), str(name))
                for symbol, name in session.execute(
                    select(SecurityAlias.symbol, Security.company_name)
                    .join(Security, Security.id == SecurityAlias.security_id)
                    .where(SecurityAlias.valid_to.is_(None))
                )
            ]
    finally:
        engine.dispose()


class NewsService:
    def __init__(self, config: Settings) -> None:
        self.config = config
        self.store = NewsStore(config.news_cache_path)
        self.analyzer = SentimentAnalyzer()

    def status(self) -> dict[str, Any]:
        state = self.store.state()
        now = datetime.now(UTC)
        started = state.get("started_at")
        next_refresh = (
            (datetime.fromisoformat(started) + timedelta(minutes=self.config.news_refresh_minutes))
            if started
            else None
        )
        running = bool(
            state.get("running")
            and started
            and now - datetime.fromisoformat(started) < timedelta(minutes=30)
        )
        last_success = state.get("last_success_at")
        stale = not last_success or now - datetime.fromisoformat(last_success) > timedelta(
            minutes=self.config.news_refresh_minutes * 2
        )
        key = self.config.firecrawl_api_key
        configured = bool(key and key.get_secret_value().strip())
        used = self.store.used_today()
        ready = self.analyzer.downloaded()
        return {
            "provider": "Firecrawl",
            "configured": configured,
            "model": MODEL_VERSION,
            "model_ready": ready,
            "running": running,
            "stale": stale,
            "last_success_at": last_success,
            "last_attempt_at": started,
            "next_refresh_at": next_refresh.isoformat() if next_refresh else None,
            "error": state.get("error"),
            "warnings": state.get("warnings", []),
            "sources": self.config.news_sources,
            "credits_reserved_today": used,
            "daily_credit_budget": self.config.news_daily_credit_budget,
            "refresh_minutes": self.config.news_refresh_minutes,
            "auto_refresh": self.config.news_auto_refresh,
            "can_refresh": configured
            and ready
            and not running
            and (next_refresh is None or next_refresh <= now)
            and used + (1 if self.config.news_rss_urls else 3)
            <= self.config.news_daily_credit_budget,
        }

    def feed(self, symbol: str | None = None) -> dict[str, Any]:
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=7)
        articles = self.store.articles()
        # Never turn a recently retrieved old story into fresh news.
        articles = [
            a
            for a in articles
            if not a.get("duplicate_of")
            and (
                not a.get("published_at")
                or cutoff <= datetime.fromisoformat(a["published_at"]) <= now
            )
        ]
        if symbol:
            articles = [a for a in articles if symbol.upper() in a["companies"]]
        articles.sort(key=lambda a: a.get("published_at") or a["retrieved_at"], reverse=True)
        return {"status": self.status(), "articles": articles[:100]}

    def prepare(self) -> str:
        if (
            not self.config.firecrawl_api_key
            or not self.config.firecrawl_api_key.get_secret_value()
        ):
            raise ProviderError(
                "Add PRISM_FIRECRAWL_API_KEY to the backend .env and restart the API"
            )
        if not self.analyzer.downloaded():
            raise ModelUnavailable("Download FinBERT with uv run python -m jobs.setup_news_model")
        return self.store.begin(self.config.news_refresh_minutes)

    def collect(self, token: str) -> None:
        warnings: list[str] = []
        added = 0
        error = None
        try:
            # Load the model before spending credits, with offline-only inference.
            self.analyzer.load()
            try:
                companies = load_companies(self.config)
            except Exception:
                companies = [(e["symbol"], e["company_name"]) for e in NIFTY_CORE_ENTITIES]
                warnings.append(
                    "Database catalogue unavailable; stock matching uses the core company list"
                )
            if not companies and not warnings:
                warnings.append(
                    "Company catalogue is empty; import the universe for stock matching"
                )
            existing = self.store.articles()
            with httpx.Client() as client:
                provider = FirecrawlProvider(self.config, self.store, client)
                candidates, discovery_warnings = provider.discover()
                warnings.extend(discovery_warnings)
                attempted = 0
                for item in candidates:
                    if self.store.recent(item["url"], MODEL_VERSION):
                        continue
                    if attempted >= self.config.news_max_articles:
                        break
                    attempted += 1
                    try:
                        article = provider.scrape(item)
                        published = article.get("published_at")
                        if published and not (
                            datetime.now(UTC) - timedelta(days=7)
                            <= datetime.fromisoformat(published)
                            <= datetime.now(UTC)
                        ):
                            continue
                        article["content_hash"] = fingerprint(article["text"])
                        previous = next(
                            (
                                old
                                for old in existing
                                if old["sentiment"]["model"] == MODEL_VERSION
                                and duplicate(article, [old])
                            ),
                            None,
                        )
                        if previous:
                            cached = {
                                **previous,
                                "url": article["url"],
                                "retrieved_at": article["retrieved_at"],
                            }
                            if previous["url"] != article["url"]:
                                cached["duplicate_of"] = previous.get(
                                    "duplicate_of", previous["url"]
                                )
                            self.store.save(cached)
                            continue
                        text = f"{article['title']}.\n{article['text']}"
                        article["sentiment"] = self.analyzer.analyze(text)
                        matches = company_passages(text, companies)
                        article["companies"] = {
                            symbol: self.analyzer.analyze(passages)
                            for symbol, passages in list(matches.items())[:20]
                        }
                        article["excerpt"] = article.pop("text")[:500]
                        self.store.save(article)
                        existing = [a for a in existing if a["url"] != article["url"]]
                        existing.append(article)
                        added += 1
                    except ProviderError as exc:
                        warnings.append(str(exc))
                if not candidates:
                    warnings.append("No articles found from the configured publishers")
                elif attempted and not added and warnings:
                    error = "No new articles could be analyzed; see collection warnings"
        except (ProviderError, RefreshBlocked, ModelUnavailable) as exc:
            error = str(exc)
        except Exception:
            logger.exception("News collection failed")
            error = "News processing failed; previously collected articles are still available"
        finally:
            self.store.finish(token, error, list(dict.fromkeys(warnings)), added)
