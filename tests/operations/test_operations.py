"""Numeric freshness, isolated DAG, alert, and incremental-scope tests."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import Alert, PipelineRun
from backend.app.operations.orchestration import DagTask, execute_daily_dag
from backend.app.operations.service import (
    AlertCandidate,
    freshness_status,
    incremental_rescore,
    persist_alert,
)


def test_freshness_hand_calculated_boundary_missing_and_no_lookahead() -> None:
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    last = now - timedelta(minutes=90)
    assert freshness_status(now, last, 60, 30) == "fresh"
    assert freshness_status(now + timedelta(seconds=1), last, 60, 30) == "stale"
    assert freshness_status(now, None, 60, 30) == "unknown"
    assert freshness_status(now, last, 60, 30) == freshness_status(now, last, 60, 30)
    with pytest.raises(ValueError, match="after evaluation"):
        freshness_status(now, now + timedelta(seconds=1), 60, 30)


def test_dag_order_retry_and_failure_isolation() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    calls: list[str] = []
    attempts = {"retry": 0}

    def succeeds() -> dict[str, object]:
        calls.append("first")
        return {"rows": 1}

    def retries() -> dict[str, object]:
        attempts["retry"] += 1
        if attempts["retry"] == 1:
            raise RuntimeError("transient")
        calls.append("retry")
        return {"rows": 2}

    def fails() -> None:
        calls.append("failed")
        raise RuntimeError("permanent")

    def after_failure() -> None:
        calls.append("after")

    with Session(engine) as session:
        result = execute_daily_dag(
            session,
            [
                DagTask("first", succeeds),
                DagTask("retry", retries),
                DagTask("failed", fails),
                DagTask("after", after_failure),
            ],
            configured_order=["first", "retry", "failed", "after"],
            config_fingerprint="f" * 64,
            retry_attempts=2,
            initial_wait_seconds=0,
            max_wait_seconds=0,
        )
        manifests = session.scalars(select(PipelineRun).order_by(PipelineRun.started_at)).all()

    assert calls == ["first", "retry", "failed", "failed", "after"]
    assert [item.status for item in result] == ["completed", "completed", "failed", "completed"]
    assert result[1].attempts == 2
    assert len(manifests) == 4
    assert manifests[2].quality_summary["last_known_good_preserved"] is True


def test_alert_dedup_and_cooldown_are_idempotent() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    now = datetime(2026, 10, 6, 12, tzinfo=UTC)
    candidate = AlertCandidate(
        "stock", "abc", "risk_jump", "Risk rose 11 points.",
        {"previous": 40, "current": 51, "threshold": 10}, 11.0, "run-1",
    )
    with Session(engine) as session:
        first, first_new = persist_alert(
            session, candidate, now=now, cooldown_minutes=60,
            config_version="1.0.0", config_fingerprint="f" * 64,
        )
        exact, exact_new = persist_alert(
            session, candidate, now=now, cooldown_minutes=60,
            config_version="1.0.0", config_fingerprint="f" * 64,
        )
        changed = AlertCandidate(**{**candidate.__dict__, "signal_key": "run-2"})
        cooled, cooled_new = persist_alert(
            session, changed, now=now + timedelta(minutes=30), cooldown_minutes=60,
            config_version="1.0.0", config_fingerprint="f" * 64,
        )
        count = len(session.scalars(select(Alert)).all())
    assert first_new is True
    assert exact_new is False and exact.id == first.id
    assert cooled_new is False and cooled.id == first.id
    assert count == 1


def test_incremental_rescore_passes_only_affected_security(monkeypatch: pytest.MonkeyPatch) -> None:
    parent_id = uuid4()
    security_id = uuid4()
    parent = SimpleNamespace(
        id=parent_id, status="completed", as_of_date=date(2026, 10, 6), config_version="1.0.0"
    )
    session = MagicMock()
    session.get.return_value = parent
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(run_id=uuid4())

    monkeypatch.setattr("backend.app.operations.service.run_stock_score_calculation", fake_run)
    incremental_rescore(
        session, security_id, parent_id, data_cutoff=datetime(2026, 10, 6, 13, tzinfo=UTC)
    )
    assert captured["security_ids"] == {security_id}
    assert captured["parent_run_id"] == parent_id
