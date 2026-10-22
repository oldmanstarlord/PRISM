from unittest.mock import Mock

import pytest

from backend.app import main


@pytest.mark.asyncio
async def test_news_schedule_starts_immediately_and_daily_in_ist(monkeypatch):
    scheduler = Mock()
    factory = Mock(return_value=scheduler)
    service = Mock()
    service.status.return_value = {"can_refresh": True}
    monkeypatch.setattr(main.settings, "news_auto_refresh", True)
    monkeypatch.setattr(main, "get_news_service", lambda: service)
    monkeypatch.setattr("apscheduler.schedulers.background.BackgroundScheduler", factory)
    async with main.lifespan(main.app):
        factory.assert_called_once_with(timezone="Asia/Kolkata")
        interval, daily = scheduler.add_job.call_args_list
        assert interval.args[1] == "interval"
        assert interval.kwargs["next_run_time"] is not None
        assert interval.kwargs["minutes"] == main.settings.news_refresh_minutes
        assert daily.args[1] == "cron"
        assert daily.kwargs["hour"] == daily.kwargs["minute"] == 0
        callback = interval.args[0]
        callback()
        service.collect_in_worker.assert_called_once_with(service.prepare.return_value)
        service.status.return_value = {"can_refresh": False}
        callback()
        assert service.prepare.call_count == 1  # Locks, cooldown and budget remain respected.
    scheduler.shutdown.assert_called_once_with(wait=False)
