"""Config-ordered DAG execution with isolated manifests and bounded retries."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session
from tenacity import Retrying, stop_after_attempt, wait_exponential

from backend.app.db.models import PipelineRun

logger = logging.getLogger("prism.operations")


@dataclass(frozen=True)
class DagTask:
    key: str
    action: Callable[[], dict[str, object] | None]


@dataclass(frozen=True)
class DagTaskResult:
    key: str
    status: str
    attempts: int
    error: str | None


def execute_daily_dag(
    session: Session,
    tasks: Sequence[DagTask],
    *,
    configured_order: list[str],
    config_fingerprint: str,
    retry_attempts: int,
    initial_wait_seconds: float,
    max_wait_seconds: float,
) -> list[DagTaskResult]:
    """Run every configured task in order; one failure never prevents later tasks."""
    by_key = {task.key: task for task in tasks}
    unknown = [key for key in configured_order if key not in by_key]
    if unknown:
        raise ValueError(f"unregistered DAG tasks: {', '.join(unknown)}")
    results: list[DagTaskResult] = []
    for key in configured_order:
        task = by_key[key]
        started = datetime.now(UTC)
        manifest = PipelineRun(
            id=uuid4(),
            workflow=f"daily_dag:{key}",
            code_version="operations-dag-v1",
            configuration_hash=config_fingerprint,
            status="running",
            started_at=started,
            completed_at=None,
            row_counts={},
            quality_summary={"order": configured_order.index(key)},
            error_summary=None,
        )
        session.add(manifest)
        session.commit()
        attempts = 0
        error: str | None = None
        try:
            retrying = Retrying(
                stop=stop_after_attempt(retry_attempts),
                wait=wait_exponential(
                    multiplier=initial_wait_seconds,
                    max=max_wait_seconds,
                ),
                reraise=True,
            )
            output: dict[str, object] | None = None
            for attempt in retrying:
                with attempt:
                    attempts += 1
                    output = task.action()
            manifest.status = "completed"
            manifest.row_counts = output or {}
        except Exception as exc:  # task boundary intentionally isolates all job failures
            error = f"{type(exc).__name__}: {exc}"
            manifest.status = "failed"
            manifest.error_summary = error[:2000]
            logger.exception(
                "dag_task_failed",
                extra={"task": key, "pipeline_run_id": str(manifest.id)},
            )
        manifest.completed_at = datetime.now(UTC)
        manifest.quality_summary = {
            **dict(manifest.quality_summary),
            "attempts": attempts,
            "last_known_good_preserved": manifest.status == "failed",
        }
        session.add(manifest)
        session.commit()
        results.append(DagTaskResult(key, manifest.status, attempts, error))
    return results


def structured_log(event: str, **fields: Any) -> dict[str, object]:
    """Return and emit a JSON-serializable structured log event."""
    payload: dict[str, object] = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }
    logger.info("%s", payload)
    return payload
