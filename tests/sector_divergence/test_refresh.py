from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from backend.app import main
from backend.app.market_data.trading_session import (
    IST,
    CalendarUnavailable,
    EquitySession,
    session_clock,
)
from backend.app.sector_divergence import refresh


def at(value):
    return datetime.fromisoformat(value).replace(tzinfo=IST)


@pytest.mark.parametrize(
    "value,opened,slot,next_at",
    [
        ("2026-10-23T09:14:59", False, None, "2026-10-23T09:15:00+05:30"),
        ("2026-10-23T09:15:00", True, "2026-10-23T09:15:00+05:30", "2026-10-23T09:45:00+05:30"),
        ("2026-10-23T09:44:59", True, "2026-10-23T09:15:00+05:30", "2026-10-23T09:45:00+05:30"),
        ("2026-10-23T09:45:00", True, "2026-10-23T09:45:00+05:30", "2026-10-23T10:15:00+05:30"),
        ("2026-10-23T15:29:59", True, "2026-10-23T15:15:00+05:30", "2026-10-26T09:15:00+05:30"),
        ("2026-10-23T15:30:00", False, None, "2026-10-26T09:15:00+05:30"),
        ("2026-10-24T11:00:00", False, None, "2026-10-26T09:15:00+05:30"),
        ("2026-10-20T11:00:00", False, None, "2026-10-21T09:15:00+05:30"),
    ],
)
def test_nse_slots_open_close_weekend_and_holiday(value, opened, slot, next_at):
    clock = session_clock(at(value))
    assert clock["market_open"] is opened
    assert clock["current_slot"] == slot
    assert clock["next_refresh_at"] == next_at
    assert session_clock(at(value).astimezone(UTC)) == clock


def test_verified_special_session_overrides_weekend():
    special = EquitySession(at("2026-11-08T14:20:00"), at("2026-11-08T15:30:00"))
    assert session_clock(at("2026-11-08T14:50:00"), {date(2026, 11, 8): special})["market_open"]
    assert not session_clock(at("2026-10-23T12:00:00"), {date(2026, 10, 23): None})["market_open"]
    with pytest.raises(CalendarUnavailable):
        session_clock(at("2028-01-03T10:00:00"))


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setattr(refresh.settings, "sector_auto_refresh", True)
    monkeypatch.setattr(
        refresh,
        "_state",
        {"running": False, "error": None, "last_attempt_at": None, "last_success_at": None},
    )
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.scalar.return_value = None
    session.add.side_effect = lambda item: setattr(item, "id", uuid4())
    run = SimpleNamespace(id=uuid4(), status="running")
    session.get.return_value = run
    monkeypatch.setattr(refresh, "SessionLocal", lambda: session)
    monkeypatch.setattr(refresh, "clock_for_session", lambda session, now: session_clock(now))
    lock = Mock()
    lock.__enter__ = Mock(return_value=lock)
    lock.__exit__ = Mock(return_value=False)
    lock.scalar.return_value = True
    monkeypatch.setattr(refresh.engine, "connect", lambda: lock)
    ingestor = Mock(
        return_value=SimpleNamespace(
            failed_symbols={},
            completed_symbols=5,
            requested_symbols=5,
            as_dict=lambda: {},
        )
    )
    monkeypatch.setattr(refresh, "ingest_nifty200_prices", ingestor)
    monkeypatch.setattr(
        refresh,
        "latest_market_snapshot",
        lambda session: (
            date(2026, 10, 23),
            at("2026-10-23T09:15:00"),
        ),
    )
    calculation = Mock(return_value=SimpleNamespace(run_id=uuid4(), score_count=15))
    monkeypatch.setattr(refresh, "persist_calculation", calculation)
    return session, lock, ingestor, calculation, run


def test_refresh_fetches_current_inputs_and_recalculates_then_avoids_repeated_slot(environment):
    session, lock, ingestor, calculate, run = environment
    refresh.refresh_if_due(at("2026-10-23T09:15:00"))
    assert ingestor.call_args.kwargs["provisional_date"] == date(2026, 10, 23)
    assert calculate.call_args.kwargs["provisional"] is True
    assert run.status == "completed"
    assert refresh._state["error"] is None
    # The completed slot is persisted, so a restarted API cannot repeat it.
    session.scalar.return_value = SimpleNamespace(status="completed")
    refresh._state["last_attempt_at"] = None
    refresh.refresh_if_due(at("2026-10-23T09:25:00"))
    assert ingestor.call_count == 1
    assert lock.execute.call_count == 2  # Shared lock is released even on an early return.


def test_refresh_pauses_after_close_and_resumes_next_session(environment):
    _, _, ingestor, _, _ = environment
    refresh.refresh_if_due(at("2026-10-23T15:30:00"))
    refresh.refresh_if_due(at("2026-10-24T10:00:00"))
    ingestor.assert_not_called()
    refresh.refresh_if_due(at("2026-10-26T09:15:00"))
    ingestor.assert_called_once()


def test_failed_or_outdated_inputs_never_publish_new_signal(environment, monkeypatch):
    _, _, ingestor, calculate, run = environment
    ingestor.return_value.failed_symbols = {"TEST": "No current price"}
    refresh.refresh_if_due(at("2026-10-23T10:15:00"))
    calculate.assert_not_called()
    assert "incomplete" in refresh._state["error"]
    assert run.status == "failed"
    ingestor.return_value.failed_symbols = {}
    monkeypatch.setattr(
        refresh,
        "latest_market_snapshot",
        lambda session: (
            date(2026, 10, 22),
            at("2026-10-22T15:30:00"),
        ),
    )
    refresh.refresh_if_due(at("2026-10-23T10:45:00"))
    calculate.assert_not_called()
    assert "today's prices" in refresh._state["error"]


@pytest.mark.asyncio
async def test_sector_schedule_is_independent_of_news(monkeypatch):
    scheduler = Mock()
    monkeypatch.setattr(main.settings, "news_auto_refresh", False)
    monkeypatch.setattr(main.settings, "sector_auto_refresh", True)
    monkeypatch.setattr(
        "apscheduler.schedulers.background.BackgroundScheduler", Mock(return_value=scheduler)
    )
    async with main.lifespan(main.app):
        scheduler.add_job.assert_called_once()
        call = scheduler.add_job.call_args
        assert call.args[0] is main.refresh_if_due
        assert call.kwargs["minutes"] == 1
        assert call.kwargs["max_instances"] == 1
