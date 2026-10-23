"""Publication windows use the publisher's timestamp, never retrieval time."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

NEWS_TIMEZONE = "Asia/Kolkata"
MARKET_TIMEZONE = ZoneInfo(NEWS_TIMEZONE)
NEWS_WINDOW_DAYS = 7


def published_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        published = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return published if published.tzinfo is not None else None


def is_in_news_window(value: object, now: datetime | None = None) -> bool:
    published = published_datetime(value)
    now = now or datetime.now(UTC)
    return published is not None and now - timedelta(days=NEWS_WINDOW_DAYS) <= published <= now


def is_current_day(value: object, now: datetime | None = None) -> bool:
    published = published_datetime(value)
    if published is None:
        return False
    now = now or datetime.now(UTC)
    return (
        published <= now
        and published.astimezone(MARKET_TIMEZONE).date() == now.astimezone(MARKET_TIMEZONE).date()
    )
