from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID

from backend.app.correlation_mst.service import PersistedMst
from backend.app.db.models import PipelineRun
from backend.app.pipeline import service
from backend.app.sector_divergence.service import PersistedCalculation


def running_record() -> PipelineRun:
    run = PipelineRun(
        workflow="daily_analysis",
        code_version="v1",
        configuration_hash="hash",
        status="running",
        started_at=datetime(2026, 10, 4, tzinfo=UTC),
    )
    run.id = UUID(int=100)
    return run


def test_daily_pipeline_publishes_layers_in_one_final_commit(monkeypatch: object) -> None:
    session = MagicMock()
    run = running_record()
    monkeypatch.setattr(service, "_new_run", lambda *_: run)  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service, "latest_market_snapshot",
        lambda *_: (date(2026, 10, 1), datetime(2026, 10, 2, tzinfo=UTC)),
    )
    layer_1_calls: list[bool] = []
    layer_2_calls: list[bool] = []
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service,
        "persist_calculation",
        lambda *_, **kwargs: (
            layer_1_calls.append(kwargs["commit"])
            or PersistedCalculation(UUID(int=1), False, 556, 2, 14)
        ),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service,
        "persist_mst",
        lambda *_, **kwargs: (
            layer_2_calls.append(kwargs["commit"])
            or PersistedMst(UUID(int=2), False, 199, 198, 1)
        ),
    )
    session.get.return_value = run

    result = service.run_daily_pipeline(
        session,
        start=date(2015, 1, 1),
        end=date(2026, 10, 1),
        snapshot_root=Path("data/raw/test"),
        skip_ingestion=True,
    )

    assert result.status == "completed"
    assert layer_1_calls == [False]
    assert layer_2_calls == [False]
    assert run.quality_summary["published"] is True
    session.commit.assert_called_once()


def test_daily_pipeline_rolls_back_derived_results_when_layer_2_fails(
    monkeypatch: object,
) -> None:
    session = MagicMock()
    run = running_record()
    monkeypatch.setattr(service, "_new_run", lambda *_: run)  # type: ignore[attr-defined]
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service, "latest_market_snapshot",
        lambda *_: (date(2026, 10, 1), datetime(2026, 10, 2, tzinfo=UTC)),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service,
        "persist_calculation",
        lambda *_, **__: PersistedCalculation(UUID(int=1), True, 556, 2, 14),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        service, "persist_mst", lambda *_, **__: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    session.get.return_value = run

    result = service.run_daily_pipeline(
        session,
        start=date(2015, 1, 1),
        end=date(2026, 10, 1),
        snapshot_root=Path("data/raw/test"),
        skip_ingestion=True,
    )

    assert result.status == "failed"
    assert result.failed_stage == "layer_2"
    assert run.quality_summary == {"stage": "layer_2", "published": False}
    session.rollback.assert_called_once()


def test_recovery_marks_only_returned_stale_runs_failed() -> None:
    session = MagicMock()
    stale = running_record()
    session.scalars.return_value.all.return_value = [stale]
    now = datetime(2026, 10, 4, 12, tzinfo=UTC)

    count = service.recover_stale_pipeline_runs(
        session, now=now, stale_after=timedelta(hours=2)
    )

    assert count == 1
    assert stale.status == "failed"
    assert stale.completed_at == now
    assert stale.quality_summary == {"stage": "recovery", "published": False}
    session.commit.assert_called_once()
