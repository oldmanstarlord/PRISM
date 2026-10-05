"""APScheduler wiring for daily EOD and filing/news polling workflows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]


def build_scheduler(
    config: dict[str, object],
    daily_action: Callable[[], None],
    poll_action: Callable[[], None],
) -> BackgroundScheduler:
    timezone = ZoneInfo(str(config["timezone"]))
    scheduler = BackgroundScheduler(timezone=timezone)
    scheduler.add_job(
        daily_action,
        "cron",
        hour=int(str(config["daily_run_hour"])),
        minute=int(str(config["daily_run_minute"])),
        id="prism_daily_eod",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        poll_action,
        "interval",
        minutes=int(str(config["near_real_time_poll_minutes"])),
        id="prism_filings_news_poll",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone),
    )
    return scheduler
