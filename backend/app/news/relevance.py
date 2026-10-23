"""Retain older event context only when a recent related report supports it.

Company mentions alone do not establish continuing relevance. Require a material
event, a shared company, and overlapping topic words. This is a transparent
heuristic, not an assertion that FinBERT understands whether an event is resolved.
"""

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.news.entity_matcher import NIFTY_CORE_ENTITIES
from backend.app.news.event_classifier import EventClassifier
from backend.app.news.publication_window import (
    NEWS_WINDOW_DAYS,
    is_in_news_window,
    published_datetime,
)

MATERIAL_EVENTS = {"guidance", "m&a", "regulation", "litigation", "product", "macro"}
STOP_WORDS = set(
    """
    about after again amid before being company companies could financial from
    have india indian limited market markets news over reports report says shares
    stock stocks that their this today update updates with will yesterday
""".split()
)


def select_active_articles(
    articles: list[dict[str, Any]],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    valid = [
        a
        for a in articles
        if not a.get("duplicate_of")
        and (published := published_datetime(a.get("published_at"))) is not None
        and published <= now
    ]
    recent = [a for a in valid if is_in_news_window(a.get("published_at"), now)]
    classifier = EventClassifier()

    def topic(article: dict[str, Any]) -> tuple[str, set[str]]:
        title = str(article.get("title", ""))
        category, _ = classifier.classify(title + " " + str(article.get("excerpt", "")))
        words = set(re.findall(r"[a-z]{4,}", title.lower())) - STOP_WORDS
        words -= {s.lower() for s in article.get("companies", {})}
        for entity in NIFTY_CORE_ENTITIES:
            if entity["symbol"] in article.get("companies", {}):
                names = " ".join([entity["company_name"], *entity["aliases"]])
                words -= set(re.findall(r"[a-z]{4,}", names.lower()))
        return category, words

    topics = {a["url"]: topic(a) for a in valid}

    def publication(article: dict[str, Any]) -> datetime:
        value = published_datetime(article["published_at"])
        assert value is not None  # Invalid dates were excluded above.
        return value

    result = []
    for article in valid:
        category, words = topics[article["url"]]
        card = {
            **article,
            "event_category": category,
            "is_retained_context": False,
            "relevance_reason": None,
            "relevance_until": None,
            "related_article_url": None,
        }
        if is_in_news_window(article.get("published_at"), now):
            result.append(card)
            continue
        if category not in MATERIAL_EVENTS:
            continue
        followups = [
            a
            for a in recent
            if set(a.get("companies", {})) & set(article.get("companies", {}))
            and topics[a["url"]][0] == category
            and len(words & topics[a["url"]][1]) >= 2
        ]
        if not followups:
            continue
        latest = max(followups, key=publication)
        published = published_datetime(latest["published_at"])
        assert published is not None
        card.update(
            is_retained_context=True,
            relevance_reason="Related company event reported again within the last 7 days.",
            relevance_until=(published + timedelta(days=NEWS_WINDOW_DAYS)).isoformat(),
            related_article_url=latest["url"],
        )
        result.append(card)
    return sorted(result, key=publication, reverse=True)
