"""Policy rule versioning and repository management (Step 11, D1)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.db.models import PolicyRule


def get_active_rules(session: Session) -> list[PolicyRule]:
    """Retrieve all currently active policy rules."""
    stmt = (
        select(PolicyRule)
        .where(PolicyRule.active.is_(True))
        .order_by(PolicyRule.rule_key.asc())
    )
    return list(session.scalars(stmt).all())


def get_rules(
    session: Session,
    active_only: bool = False,
    category: str | None = None,
) -> list[PolicyRule]:
    """Retrieve policy rules with optional active and category filters."""
    stmt = select(PolicyRule)
    if active_only:
        stmt = stmt.where(PolicyRule.active.is_(True))
    if category:
        stmt = stmt.where(PolicyRule.match_category == category.strip())

    stmt = stmt.order_by(PolicyRule.rule_key.asc(), desc(PolicyRule.version))
    return list(session.scalars(stmt).all())


def bump_version_string(current_version: str) -> str:
    """Increment minor version string (e.g. 1.0.0 -> 1.1.0)."""
    parts = current_version.split(".")
    if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
        return f"{parts[0]}.{int(parts[1]) + 1}.0"
    return f"{current_version}.1"


def create_or_version_rule(
    session: Session,
    rule_key: str,
    description: str,
    match_keywords: list[str],
    match_category: str,
    affected_industries: list[str],
    direction: str,
    severity: float,
    rationale: str,
    reviewer: str,
    active: bool = True,
) -> PolicyRule:
    """Create a new version of a policy rule (D1).

    Enforces mandatory economic rationale and reviewer accountability.
    """
    clean_rationale = rationale.strip()
    if not clean_rationale:
        raise ValueError(
            "An explicit economic rationale is strictly required for every policy rule."
        )

    clean_reviewer = reviewer.strip()
    if not clean_reviewer:
        raise ValueError("A reviewer identifier is required for policy rule auditability.")

    if severity < 1.0 or severity > 10.0:
        raise ValueError("Severity must be between 1.0 and 10.0 points.")

    if direction not in ("headwind", "tailwind", "ambiguous"):
        raise ValueError("Direction must be 'headwind', 'tailwind', or 'ambiguous'.")

    # Find existing rules for this key
    existing_rules = session.scalars(
        select(PolicyRule)
        .where(PolicyRule.rule_key == rule_key)
        .order_by(desc(PolicyRule.created_at))
    ).all()

    if existing_rules:
        latest = existing_rules[0]
        new_version = bump_version_string(latest.version)
        # Deactivate older active rows for this rule key
        for old in existing_rules:
            if old.active:
                old.active = False
    else:
        new_version = "1.0.0"

    new_rule = PolicyRule(
        id=uuid4(),
        rule_key=rule_key,
        description=description.strip(),
        match_keywords=match_keywords,
        match_category=match_category.strip(),
        affected_industries=affected_industries,
        direction=direction,
        severity=severity,
        rationale=clean_rationale,
        reviewer=clean_reviewer,
        version=new_version,
        active=active,
    )

    session.add(new_rule)
    session.commit()
    return new_rule
