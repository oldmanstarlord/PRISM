"""Today's Indian-market news uses the publisher's timestamp, never retrieval time."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

NEWS_TIMEZONE = "Asia/Kolkata"
MARKET_TIMEZONE = ZoneInfo(NEWS_TIMEZONE)


def is_current_day(value: object, now: datetime | None = None) -> bool:
    if not isinstance(value, str):
        return False
    try:
        published = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if published.tzinfo is None:
        return False
    now = now or datetime.now(UTC)
    return (
        published <= now
        and published.astimezone(MARKET_TIMEZONE).date()
        == now.astimezone(MARKET_TIMEZONE).date()
    )
