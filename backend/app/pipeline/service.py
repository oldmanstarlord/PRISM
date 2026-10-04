"""Fail-closed orchestration for the daily PRISM publication pipeline."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.correlation_mst.service import PersistedMst, persist_mst
from backend.app.db.models import PipelineRun
from backend.app.market_data.service import ingest_nifty200_prices
from backend.app.market_data.types import IngestionSummary
from backend.app.sector_divergence.service import (
    PersistedCalculation,
    latest_market_snapshot,
    persist_calculation,
)

WORKFLOW = "daily_analysis"
CODE_VERSION = "daily-analysis-v1"


@dataclass(frozen=True, slots=True)
class DailyPipelineResult:
    run_id: UUID
    status: str
    published_market_date: date | None
    layer_1_run_id: UUID | None
    layer_2_run_id: UUID | None
    failed_stage: str | None
    error: str | None


def _new_run(session: Session, started_at: datetime) -> PipelineRun:
    run = PipelineRun(
        workflow=WORKFLOW,
        code_version=CODE_VERSION,
        configuration_hash="daily-analysis-v1",
        status="running",
        started_at=started_at,
        quality_summary={"stage": "starting"},
    )
    session.add(run)
    session.commit()
    return run


def _fail_run(session: Session, run_id: UUID, stage: str, exc: Exception) -> DailyPipelineResult:
    session.rollback()
    run = session.get(PipelineRun, run_id)
    if run is None:
        raise RuntimeError(f"Pipeline run {run_id} disappeared") from exc
    message = f"{type(exc).__name__}: {exc}"
    run.status = "failed"
    run.completed_at = datetime.now(UTC)
    run.quality_summary = {"stage": stage, "published": False}
    run.error_summary = message
    session.commit()
    return DailyPipelineResult(run_id, "failed", None, None, None, stage, message)


def run_daily_pipeline(
    session: Session,
    *,
    start: date,
    end: date,
    snapshot_root: Path,
    max_workers: int = 8,
    skip_ingestion: bool = False,
    ingestor: Callable[..., IngestionSummary] = ingest_nifty200_prices,
) -> DailyPipelineResult:
    """Ingest, calculate, and atomically publish both analytical layers."""
    started_at = datetime.now(UTC)
    run = _new_run(session, started_at)
    run_id = run.id
    stage = "ingestion"
    ingestion_summary: IngestionSummary | None = None
    try:
        if not skip_ingestion:
            run.quality_summary = {"stage": stage}
            session.commit()
            ingestion_summary = ingestor(
                session,
                start=start,
                end=end,
                snapshot_root=snapshot_root,
                max_workers=max_workers,
            )
            if ingestion_summary.failed_symbols:
                raise RuntimeError(
                    "Market-data ingestion was partial: "
                    + json.dumps(ingestion_summary.failed_symbols, sort_keys=True)
                )

        market_date, cutoff = latest_market_snapshot(session)
        calculation_time = datetime.now(UTC)
        stage = "layer_1"
        layer_1: PersistedCalculation = persist_calculation(
            session,
            signal_date=market_date,
            lookback_start=market_date - timedelta(days=180),
            data_cutoff=cutoff,
            computed_at=calculation_time,
            commit=False,
        )
        stage = "layer_2"
        layer_2: PersistedMst = persist_mst(
            session,
            window_end=market_date,
            lookback_start=market_date - timedelta(days=220),
            data_cutoff=cutoff,
            computed_at=calculation_time,
            commit=False,
        )
        completed = session.get(PipelineRun, run_id)
        if completed is None:
            raise RuntimeError(f"Pipeline run {run_id} disappeared")
        completed.status = "completed"
        completed.completed_at = datetime.now(UTC)
        completed.row_counts = {
            "market_data": ingestion_summary.as_dict() if ingestion_summary else {"skipped": True},
            "layer_1_scores": layer_1.score_count,
            "layer_2_nodes": layer_2.node_count,
            "layer_2_edges": layer_2.edge_count,
        }
        completed.quality_summary = {
            "stage": "published",
            "published": True,
            "market_date": market_date.isoformat(),
            "data_cutoff": cutoff.isoformat(),
        }
        session.commit()
        return DailyPipelineResult(
            run_id,
            "completed",
            market_date,
            layer_1.run_id,
            layer_2.run_id,
            None,
            None,
        )
    except Exception as exc:
        return _fail_run(session, run_id, stage, exc)


def recover_stale_pipeline_runs(
    session: Session,
    *,
    now: datetime | None = None,
    stale_after: timedelta = timedelta(hours=2),
) -> int:
    """Mark abandoned running workflows failed without touching published results."""
    current_time = now or datetime.now(UTC)
    cutoff = current_time - stale_after
    runs = session.scalars(
        select(PipelineRun).where(
            PipelineRun.status == "running",
            PipelineRun.started_at < cutoff,
        )
    ).all()
    for run in runs:
        run.status = "failed"
        run.completed_at = current_time
        run.quality_summary = {"stage": "recovery", "published": False}
        run.error_summary = "Recovered abandoned running pipeline"
    session.commit()
    return len(runs)
