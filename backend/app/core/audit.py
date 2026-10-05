"""Audit logging helper for PRISM operational compliance (NFR-1, D7)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.db.models import AuditLog


def write_audit(
    session: Session,
    subject: str,
    event_type: str,
    run_id: UUID | None,
    reason: str,
    inputs_ref: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an immutable audit entry in audit_log."""
    entry = AuditLog(
        subject=subject,
        event_type=event_type,
        run_id=run_id,
        reason=reason,
        inputs_ref=inputs_ref or {},
    )
    session.add(entry)
    return entry
