"""Canonical provenance labels for news items verified on official live feeds."""

VERIFIED_NEWS_SOURCE_MAP: dict[str, str] = {
    "RBI": "RBI_RSS_VERIFIED",
    "SEBI": "SEBI_RSS_VERIFIED",
}
VERIFIED_NEWS_SOURCES: tuple[str, ...] = tuple(VERIFIED_NEWS_SOURCE_MAP.values())


def base_news_source(source: str) -> str:
    """Map a verified storage label back to its configured source owner key."""
    for base, verified in VERIFIED_NEWS_SOURCE_MAP.items():
        if source == verified:
            return base
    return source
