"""Shared pytest fixtures for PRISM."""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import engine, get_session
from backend.app.main import app


@pytest.fixture(autouse=True)
def isolated_session() -> Generator[Session, None, None]:
    """Run each test inside a database transaction that is always rolled back.

    This preserves access to migration seeds while preventing API tests and shared
    fixtures from persisting test rows in the configured database.
    """
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    def override_session() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_session] = override_session
    try:
        yield db
    finally:
        app.dependency_overrides.pop(get_session, None)
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def session(isolated_session: Session) -> Session:
    """Yield the per-test rollback-only database session."""
    return isolated_session
