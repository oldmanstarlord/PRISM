"""NSE equity session clock; database rows override the bundled 2026 calendar.

Sources: NSE/CMTR/71775 (2026 holidays), NSE/CMTR/72349 (Budget Sunday),
https://www.nseindia.com/static/market-data/market-timings .
Unknown years require verified TradingCalendar rows, rather than guessed holidays.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
INTERVAL = timedelta(minutes=30)
HOLIDAYS_2026 = {
    date.fromisoformat(day)
    for day in (
        "2026-01-26",
        "2026-03-03",
        "2026-03-26",
        "2026-03-31",
        "2026-04-03",
        "2026-04-14",
        "2026-05-01",
        "2026-05-28",
        "2026-06-26",
        "2026-09-14",
        "2026-10-02",
        "2026-10-20",
        "2026-11-10",
        "2026-11-24",
        "2026-12-25",
    )
}
BUDGET_SESSION = date(2026, 2, 1)


class CalendarUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class EquitySession:
    opens_at: datetime
    closes_at: datetime

    def slot(self, now: datetime) -> datetime | None:
        if not self.opens_at <= now < self.closes_at:
            return None
        return self.opens_at + (now - self.opens_at) // INTERVAL * INTERVAL


def regular_session(day: date) -> EquitySession | None:
    if day.year != 2026:
        raise CalendarUnavailable("Verified NSE trading calendar is required for this year")
    if day in HOLIDAYS_2026 or (day.weekday() >= 5 and day != BUDGET_SESSION):
        return None
    return EquitySession(
        datetime.combine(day, time(9, 15), IST), datetime.combine(day, time(15, 30), IST)
    )


def session_clock(
    now: datetime | None = None,
    overrides: dict[date, EquitySession | None] | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Session clock requires a timezone-aware timestamp")
    overrides = overrides or {}
    day = now.astimezone(IST).date()

    def resolve(day: date) -> EquitySession | None:
        return overrides[day] if day in overrides else regular_session(day)

    session = resolve(day)
    slot = session.slot(now) if session else None
    next_refresh = None
    if session and now < session.opens_at:
        next_refresh = session.opens_at
    elif session and slot is not None and slot + INTERVAL < session.closes_at:
        next_refresh = slot + INTERVAL
    if next_refresh is None:
        for offset in range(1, 15):
            candidate = resolve(day + timedelta(days=offset))
            if candidate:
                next_refresh = candidate.opens_at
                break
    return {
        "market_open": slot is not None,
        "session_open": session.opens_at.isoformat() if session else None,
        "session_close": session.closes_at.isoformat() if session else None,
        "current_slot": slot.isoformat() if slot else None,
        "next_refresh_at": next_refresh.isoformat() if next_refresh else None,
        "timezone": "Asia/Kolkata",
        "refresh_minutes": 30,
    }
