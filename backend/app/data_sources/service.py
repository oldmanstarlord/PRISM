"""Read and update the auditable data-source registry."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data_sources.schemas import DataSourceOut
from backend.app.db.models import DataSource


def registry_freshness_status(
    now: datetime,
    last_success_at: datetime | None,
    expected_cadence_minutes: int,
    grace_minutes: int,
) -> str:
    """Classify a source; one that never succeeded is explicitly missing."""
    if last_success_at is None:
        return "missing"
    if last_success_at.tzinfo is None or last_success_at.utcoffset() is None:
        raise ValueError("last_success_at must be timezone-aware")
    if last_success_at > now:
        raise ValueError("last_success_at cannot be after evaluation time")
    deadline = last_success_at + timedelta(minutes=expected_cadence_minutes + grace_minutes)
    return "stale" if now > deadline else "fresh"


def list_data_sources(session: Session) -> list[DataSourceOut]:
    """Return every registered dataset, including manual and TBD sources."""
    sources = session.scalars(
        select(DataSource).order_by(DataSource.dataset, DataSource.source_key)
    ).all()
    policies = source_policy(session)
    now = datetime.now(UTC)
    return [
        DataSourceOut(
            source_key=row.source_key,
            dataset=row.dataset,
            owner=row.owner,
            access_method=row.access_method,
            terms_url=row.terms_url,
            license_note=row.license_note,
            cadence=row.cadence,
            expected_grace_days=row.expected_grace_days,
            status=row.status,
            freshness_status=registry_freshness_status(
                now,
                row.last_success_at,
                policies[row.source_key]["expected_cadence_minutes"],
                policies[row.source_key]["grace_minutes"],
            )
            if row.source_key in policies
            else "missing",
            last_verified_at=row.last_verified_at,
            last_success_at=row.last_success_at,
            notes=row.notes,
        )
        for row in sources
    ]


def mark_source_success(
    session: Session,
    source_key: str,
    *,
    succeeded_at: datetime | None = None,
    verified: bool = False,
) -> None:
    """Record a real successful adapter call/import without fabricating a data date."""
    row = session.get(DataSource, source_key)
    if row is None:
        raise ValueError(f"unregistered data source: {source_key}")
    timestamp = succeeded_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("source success timestamp must be timezone-aware")
    row.last_success_at = timestamp
    if verified:
        row.last_verified_at = timestamp
    session.add(row)


def source_policy(session: Session) -> dict[str, dict[str, int]]:
    """Load cadence and grace exclusively from approved versioned configuration."""
    from backend.app.db.models import ModelConfig

    row = session.scalars(
        select(ModelConfig)
        .where(
            ModelConfig.config_key == "data_source_policy",
            ModelConfig.status == "approved",
        )
        .order_by(ModelConfig.created_at.desc())
    ).first()
    if row is None:
        return {}
    raw_sources: Any = row.configuration.get("sources", {})
    if not isinstance(raw_sources, dict):
        raise ValueError("data_source_policy.sources must be an object")
    policies: dict[str, dict[str, int]] = {}
    for key, raw in raw_sources.items():
        if not isinstance(key, str) or not isinstance(raw, dict):
            continue
        policies[key] = {
            "expected_cadence_minutes": int(raw["expected_cadence_minutes"]),
            "grace_minutes": int(raw["grace_minutes"]),
        }
    return policies
