"""Shared pytest fixtures for PRISM conforming to Rule D10."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers and apply test database safety guard."""
    config.addinivalue_line("markers", "db: mark test as requiring a database connection")

    test_db_url = os.environ.get("PRISM_TEST_DATABASE_URL")
    prod_db_url = os.environ.get("PRISM_DATABASE_URL")

    if test_db_url:
        if "supabase" in test_db_url.lower():
            raise pytest.UsageError(
                "PRISM_TEST_DATABASE_URL must not point to Supabase (production safety rule D10)"
            )
        if prod_db_url and test_db_url.strip() == prod_db_url.strip():
            raise pytest.UsageError(
                "PRISM_TEST_DATABASE_URL must not equal PRISM_DATABASE_URL "
                "(production safety rule D10)"
            )
        # Point the application's database configuration to the test database
        os.environ["PRISM_DATABASE_URL"] = test_db_url


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Tag database-dependent tests and skip them if test database is not configured."""
    db_fixtures = {"session", "isolated_session", "client"}
    test_db_url = os.environ.get("PRISM_TEST_DATABASE_URL")

    for item in items:
        fixture_names = getattr(item, "fixturenames", [])
        # Tests using mock_session don't require a live database
        if "mock_session" in fixture_names:
            continue

        if any(f in fixture_names for f in db_fixtures) or "db" in item.keywords:
            item.add_marker(pytest.mark.db)
            if not test_db_url:
                item.add_marker(
                    pytest.mark.skip(
                        reason="PRISM_TEST_DATABASE_URL is not set; skipping database-backed test"
                    )
                )


@pytest.fixture
def isolated_session() -> Generator[Session, None, None]:
    """Run each test inside a database transaction that is always rolled back.

    Preserves migration seeds while preventing tests from persisting rows.
    """
    test_db_url = os.environ.get("PRISM_TEST_DATABASE_URL")
    if not test_db_url:
        pytest.skip("PRISM_TEST_DATABASE_URL is not set; skipping database-backed test")

    from backend.app.db.session import engine, get_session
    from backend.app.main import app

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


@pytest.fixture
def client(session: Session) -> TestClient:
    """Yield a TestClient bound to the per-test isolated database session."""
    from backend.app.main import app

    return TestClient(app)
