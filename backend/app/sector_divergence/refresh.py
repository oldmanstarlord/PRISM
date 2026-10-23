"""Refresh price inputs and publish divergence once per open-market half-hour."""

import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

from sqlalchemy import desc, select, text, update

from backend.app.core.config import settings
from backend.app.db.models import PipelineRun, TradingCalendar
from backend.app.db.session import SessionLocal, engine
from backend.app.market_data.service import ingest_nifty200_prices
from backend.app.market_data.trading_session import (
    IST,
    CalendarUnavailable,
    EquitySession,
    session_clock,
)
from backend.app.sector_divergence.service import latest_market_snapshot, persist_calculation

logger = logging.getLogger(__name__)
WORKFLOW = "sector_divergence_intraday"
ADVISORY_LOCK_ID = 73402811
_local_lock = Lock()
_state: dict[str, Any] = {
    "running": False,
    "error": None,
    "last_attempt_at": None,
    "last_success_at": None,
}


def clock_for_session(session: Any, now: datetime) -> dict[str, Any]:
    day = now.astimezone(IST).date()
    rows = session.scalars(
        select(TradingCalendar).where(
            TradingCalendar.exchange == "NSE",
            TradingCalendar.trading_date >= day,
            TradingCalendar.trading_date <= day + timedelta(days=14),
        )
    ).all()
    overrides: dict[date, EquitySession | None] = {}
    for row in rows:
        if not row.is_trading_day:
            overrides[row.trading_date] = None
        elif row.session_open and row.session_close:
            if row.session_open.tzinfo is None or row.session_close.tzinfo is None:
                raise CalendarUnavailable("NSE calendar session times must include a timezone")
            overrides[row.trading_date] = EquitySession(row.session_open, row.session_close)
        elif row.trading_date.weekday() >= 5:
            raise CalendarUnavailable("Special NSE session requires verified opening/closing times")
    return session_clock(now, overrides)


def refresh_status() -> dict[str, Any]:
    now = datetime.now(UTC)
    try:
        with SessionLocal() as session:
            clock = clock_for_session(session, now)
            last_success = session.scalar(
                select(PipelineRun)
                .where(
                    PipelineRun.workflow == WORKFLOW,
                    PipelineRun.status == "completed",
                )
                .order_by(desc(PipelineRun.completed_at))
                .limit(1)
            )
            if last_success is not None and last_success.completed_at is not None:
                _state["last_success_at"] = last_success.completed_at.isoformat()
            latest = session.scalar(
                select(PipelineRun)
                .where(PipelineRun.workflow == WORKFLOW)
                .order_by(desc(PipelineRun.started_at))
                .limit(1)
            )
            if latest is not None:
                _state["last_attempt_at"] = latest.started_at.isoformat()
                _state["running"] = latest.status == "running"
                _state["error"] = latest.error_summary if latest.status == "failed" else None
    except Exception:
        try:
            clock = session_clock(now)
        except CalendarUnavailable:
            clock = {
                "market_open": False,
                "next_refresh_at": None,
                "refresh_minutes": 30,
                "timezone": "Asia/Kolkata",
            }
        clock["calendar_warning"] = "Database calendar unavailable; bundled 2026 calendar shown"
    return {**clock, **_state, "enabled": settings.sector_auto_refresh}


def refresh_if_due(now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    if not settings.sector_auto_refresh or not _local_lock.acquire(blocking=False):
        return
    run_id = None
    try:
        # Retry provider/database failures after five minutes, without moving the
        # successful half-hour schedule. The PostgreSQL lock covers all API workers.
        attempted = _state.get("last_attempt_at")
        if attempted and now - datetime.fromisoformat(attempted) < timedelta(minutes=5):
            return
        with SessionLocal() as session:
            clock = clock_for_session(session, now)
            if not clock["market_open"]:
                return
            slot = clock["current_slot"]
            with engine.connect() as lock_connection:
                acquired = lock_connection.scalar(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": ADVISORY_LOCK_ID},
                )
                if not acquired:
                    return
                try:
                    existing = session.scalar(
                        select(PipelineRun)
                        .where(
                            PipelineRun.workflow == WORKFLOW,
                            PipelineRun.configuration_hash == slot,
                            PipelineRun.status == "completed",
                        )
                        .limit(1)
                    )
                    if existing is not None:
                        return
                    # Acquiring the shared session lock proves any earlier owner
                    # has stopped. Record interrupted runs before retrying a slot.
                    session.execute(
                        update(PipelineRun)
                        .where(
                            PipelineRun.workflow == WORKFLOW,
                            PipelineRun.status == "running",
                        )
                        .values(
                            status="failed",
                            completed_at=now,
                            error_summary="Sector refresh interrupted before publication",
                        )
                    )
                    _state.update(running=True, error=None, last_attempt_at=now.isoformat())
                    run = PipelineRun(
                        workflow=WORKFLOW,
                        code_version="intraday-divergence-v1",
                        configuration_hash=slot,
                        status="running",
                        started_at=now,
                        quality_summary={"stage": "ingestion", "slot": slot},
                    )
                    session.add(run)
                    session.commit()
                    run_id = run.id
                    today = now.astimezone(IST).date()
                    summary = ingest_nifty200_prices(
                        session,
                        start=today - timedelta(days=220),
                        end=today,
                        snapshot_root=Path(__file__).resolve().parents[3] / "data/raw/yfinance",
                        provisional_date=today,
                    )
                    if (
                        summary.failed_symbols
                        or summary.completed_symbols != summary.requested_symbols
                    ):
                        raise RuntimeError(
                            "Current-session price coverage is incomplete; "
                            "keeping the previous signal"
                        )
                    signal_date, cutoff = latest_market_snapshot(session)
                    if signal_date != today:
                        raise RuntimeError(
                            "Provider has not supplied today's prices; keeping the previous signal"
                        )
                    result = persist_calculation(
                        session,
                        signal_date=today,
                        lookback_start=today - timedelta(days=220),
                        data_cutoff=cutoff,
                        provisional=True,
                        commit=False,
                    )
                    if not result.score_count:
                        raise RuntimeError(
                            "No valid divergence scores; keeping the previous signal"
                        )
                    saved_run = session.get(PipelineRun, run_id)
                    if saved_run is None:
                        raise RuntimeError("Sector refresh run disappeared")
                    run = saved_run
                    run.status = "completed"
                    run.completed_at = datetime.now(UTC)
                    run.quality_summary = {
                        "stage": "published",
                        "slot": slot,
                        "layer_1_run_id": str(result.run_id),
                    }
                    run.row_counts = summary.as_dict()
                    session.commit()
                    _state.update(last_success_at=run.completed_at.isoformat(), error=None)
                finally:
                    # A pooled connection must never retain a session advisory lock.
                    lock_connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": ADVISORY_LOCK_ID}
                    )
                    lock_connection.commit()
    except Exception as exc:
        _state.update(
            last_attempt_at=now.isoformat(),
            error=(
                str(exc)
                if isinstance(exc, (CalendarUnavailable, RuntimeError))
                else "Sector refresh failed: database or market-data provider unavailable"
            ),
        )
        logger.warning("Sector refresh failed (%s)", type(exc).__name__)
        if run_id is not None:
            try:
                with SessionLocal() as session:
                    failed_run = session.get(PipelineRun, run_id)
                    if failed_run is None:
                        return
                    failed_run.status = "failed"
                    failed_run.completed_at = datetime.now(UTC)
                    failed_run.error_summary = _state["error"]
                    session.commit()
            except Exception:
                logger.warning("Could not save sector refresh failure")
    finally:
        _state["running"] = False
        _local_lock.release()
