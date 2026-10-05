"""Test policy rule versioning and mandatory economic rationale constraints (Step 11, D1)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base
from backend.app.policy.rules import create_or_version_rule, get_rules


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_rule_requires_written_economic_rationale(db_session: Session):
    """Verify that creating a rule without an explicit economic rationale fails."""
    with pytest.raises(ValueError, match="economic rationale is strictly required"):
        create_or_version_rule(
            session=db_session,
            rule_key="POL_TEST_RULE_V1",
            description="Test rule description",
            match_keywords=["test"],
            match_category="test",
            affected_industries=["Banking"],
            direction="headwind",
            severity=5.0,
            rationale="   ",  # Empty rationale
            reviewer="Risk Analyst",
        )


def test_rule_requires_reviewer_identifier(db_session: Session):
    """Verify that creating a rule without a reviewer identifier fails."""
    with pytest.raises(ValueError, match="reviewer identifier is required"):
        create_or_version_rule(
            session=db_session,
            rule_key="POL_TEST_RULE_V1",
            description="Test rule description",
            match_keywords=["test"],
            match_category="test",
            affected_industries=["Banking"],
            direction="headwind",
            severity=5.0,
            rationale="Valid economic transmission rationale explaining the mechanism.",
            reviewer=" ",  # Empty reviewer
        )


def test_rule_versioning_and_deactivation_of_predecessor(db_session: Session):
    """Verify rule version increments (1.0.0 -> 1.1.0) and deactivates previous version."""
    # 1. Create version 1.0.0
    r1 = create_or_version_rule(
        session=db_session,
        rule_key="POL_RATE_HIKE",
        description="Initial rate hike rule",
        match_keywords=["rate hike"],
        match_category="monetary",
        affected_industries=["Banking"],
        direction="headwind",
        severity=6.0,
        rationale="Initial rationale explaining funding cost increase.",
        reviewer="Analyst A",
        active=True,
    )
    assert r1.version == "1.0.0"
    assert r1.active is True

    # 2. Update rule: creates version 1.1.0
    r2 = create_or_version_rule(
        session=db_session,
        rule_key="POL_RATE_HIKE",
        description="Updated rate hike rule with tighter keywords",
        match_keywords=["rate hike", "repo rate increase"],
        match_category="monetary",
        affected_industries=["Banking", "Realty"],
        direction="headwind",
        severity=7.0,
        rationale=(
            "Expanded rationale covering both funding cost and mortgage loan demand contraction."
        ),
        reviewer="Senior Analyst B",
        active=True,
    )
    assert r2.version == "1.1.0"
    assert r2.active is True

    # Check predecessor was deactivated
    db_session.refresh(r1)
    assert r1.active is False

    # Check both rows exist in history
    all_versions = get_rules(db_session)
    assert len(all_versions) == 2
    assert [r.version for r in all_versions] == ["1.1.0", "1.0.0"]
