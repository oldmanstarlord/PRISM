"""Shared pytest fixtures for PRISM."""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Yield a database session and close it after the test."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
