"""Multi-tenant Journal (Research Notes & Investment Decisions) persistence tests."""

from collections.abc import Generator
from datetime import date
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.models import Base, JournalDecision, JournalNote
from backend.app.db.session import get_session
from backend.app.main import app

USER_A_ID = UUID("00000000-0000-0000-0000-000000000001")
USER_B_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def journal_db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    # Pre-seed note and decision for User A
    note_a = JournalNote(
        id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        owner_id=USER_A_ID,
        symbol="TCS",
        content="Confidential Q3 Earnings Note for User A",
        tags=["quarterly", "tcs"],
    )
    decision_a = JournalDecision(
        id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"),
        owner_id=USER_A_ID,
        symbol="TCS",
        decision_type="BUY",
        decision_date=date(2026, 1, 15),
        rationale="Strong pipeline and margin recovery",
        tags=["conviction"],
        snapshot={"risk_score": 38.5, "risk_label": "Balanced"},
    )
    session.add(note_a)
    session.add(decision_a)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_unauthorized_requests_rejected(journal_db_session: Session) -> None:
    """Requests without auth credentials must be rejected with 401."""
    app.dependency_overrides[get_session] = lambda: journal_db_session
    client = TestClient(app)

    try:
        resp = client.get("/api/v1/journal/notes")
        assert resp.status_code == 401

        resp = client.post(
            "/api/v1/journal/notes",
            json={"symbol": "INFY", "content": "Test note", "tags": []},
        )
        assert resp.status_code == 401

        resp = client.get("/api/v1/journal/decisions")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_user_isolation_notes_and_decisions(journal_db_session: Session) -> None:
    """User B cannot see, modify, or delete User A's notes and decisions."""
    app.dependency_overrides[get_session] = lambda: journal_db_session
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=USER_B_ID, email="user_b@prism.local"
    )
    client = TestClient(app)

    note_a_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    decision_a_id = "dddddddd-dddd-dddd-dddd-dddddddddddd"

    try:
        # 1. User B lists notes -> User A's note must NOT be returned
        resp = client.get("/api/v1/journal/notes")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

        # 2. User B tries to update User A's note -> 404
        resp = client.post(
            "/api/v1/journal/notes",
            json={
                "id": note_a_id,
                "symbol": "TCS",
                "content": "Malicious overwrite by User B",
                "tags": [],
            },
        )
        assert resp.status_code == 404

        # 3. User B tries to delete User A's note -> 404
        resp = client.delete(f"/api/v1/journal/notes/{note_a_id}")
        assert resp.status_code == 404

        # 4. User B lists decisions -> User A's decision must NOT be returned
        resp = client.get("/api/v1/journal/decisions")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

        # 5. User B tries to update User A's decision -> 404
        resp = client.post(
            "/api/v1/journal/decisions",
            json={
                "id": decision_a_id,
                "symbol": "TCS",
                "decision_type": "SELL",
                "decision_date": "2026-02-01",
                "rationale": "Tampering by User B",
                "tags": [],
            },
        )
        assert resp.status_code == 404

        # 6. User B tries to delete User A's decision -> 404
        resp = client.delete(f"/api/v1/journal/decisions/{decision_a_id}")
        assert resp.status_code == 404

    finally:
        app.dependency_overrides.clear()


def test_user_a_crud_operations(journal_db_session: Session) -> None:
    """User A can create, read, filter, update, and delete their own notes and decisions."""
    app.dependency_overrides[get_session] = lambda: journal_db_session
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=USER_A_ID, email="user_a@prism.local"
    )
    client = TestClient(app)

    try:
        # 1. Read existing note
        resp = client.get("/api/v1/journal/notes")
        assert resp.status_code == 200
        notes = resp.json()
        assert len(notes) == 1
        assert notes[0]["symbol"] == "TCS"
        assert "Confidential Q3" in notes[0]["content"]

        # 2. Filter by symbol
        resp = client.get("/api/v1/journal/notes?symbol=TCS")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = client.get("/api/v1/journal/notes?symbol=RELIANCE")
        assert resp.status_code == 200
        assert len(resp.json()) == 0

        # 3. Create new note
        resp = client.post(
            "/api/v1/journal/notes",
            json={"symbol": "INFY", "content": "Growth prospects looking steady", "tags": ["it"]},
        )
        assert resp.status_code == 201
        created_note = resp.json()
        assert created_note["symbol"] == "INFY"
        assert created_note["owner_id"] == str(USER_A_ID)

        # 4. Verify 2 notes now exist
        resp = client.get("/api/v1/journal/notes")
        assert len(resp.json()) == 2

        # 5. Update note
        resp = client.post(
            "/api/v1/journal/notes",
            json={
                "id": created_note["id"],
                "symbol": "INFY",
                "content": "Updated thesis: high conviction growth",
                "tags": ["it", "conviction"],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["content"] == "Updated thesis: high conviction growth"

        # 6. Delete note
        resp = client.delete(f"/api/v1/journal/notes/{created_note['id']}")
        assert resp.status_code == 204

        # 7. Create decision
        resp = client.post(
            "/api/v1/journal/decisions",
            json={
                "symbol": "HDFCBANK",
                "decision_type": "Hold",
                "decision_date": "2026-02-10",
                "rationale": "Monitor credit-deposit ratio",
                "tags": ["banking"],
                "snapshot": {"risk_score": 42.0},
            },
        )
        assert resp.status_code == 201
        dec = resp.json()
        assert dec["symbol"] == "HDFCBANK"
        assert dec["decision_type"] == "HOLD"
        assert dec["owner_id"] == str(USER_A_ID)

        # 8. Sync endpoint
        resp = client.post(
            "/api/v1/journal/sync",
            json={
                "notes": [
                    {"symbol": "SBIN", "content": "PSU bank momentum", "tags": ["banking"]},
                ],
                "decisions": [
                    {
                        "symbol": "SBIN",
                        "decision_type": "Buy",
                        "decision_date": "2026-02-12",
                        "rationale": "Valuation discount",
                        "tags": [],
                    }
                ],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["notes_synced"] == 1
        assert resp.json()["decisions_synced"] == 1

    finally:
        app.dependency_overrides.clear()
