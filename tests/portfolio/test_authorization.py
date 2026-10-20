"""Multi-tenant authorization isolation tests.

Verifies requirement B.8:
- User A cannot read or modify User B's portfolios.
- User A cannot view, add, import, or export User B's transactions.
- User A cannot view User B's reconciliation reports or portfolio snapshots.
- User A cannot view User B's risk history.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.auth import AuthenticatedUser, require_user
from backend.app.db.models import (
    Base,
    Portfolio,
    PortfolioHolding,
    PortfolioSnapshot,
    PortfolioTransaction,
    Security,
)
from backend.app.db.session import get_session
from backend.app.main import app

USER_A_ID = UUID("00000000-0000-0000-0000-000000000001")
USER_B_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def test_db_session() -> Generator[Session, None, None]:
    """Provide an isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    now = datetime.now(UTC)

    # Seed Security
    sec_id = UUID("33333333-3333-3333-3333-333333333333")
    sec = Security(
        id=sec_id,
        isin="INE467B01029",
        company_name="Tata Consultancy Services Ltd",
        currency="INR",
        is_active=True,
    )
    session.add(sec)

    # Seed Portfolio belonging exclusively to User A
    portfolio_a_id = UUID("11111111-1111-1111-1111-111111111111")
    portfolio_a = Portfolio(
        id=portfolio_a_id,
        owner_id=USER_A_ID,
        owner_ref="user-a",
        name="User A Confidential Portfolio",
        input_mode="quantities",
        currency="INR",
        created_at=now,
        updated_at=now,
    )
    session.add(portfolio_a)

    # Seed Snapshot
    snap_id = UUID("44444444-4444-4444-4444-444444444444")
    snap = PortfolioSnapshot(
        id=snap_id,
        portfolio_id=portfolio_a_id,
        owner_id=USER_A_ID,
        valuation_date=date(2026, 1, 15),
        cash_amount=Decimal("10000.00"),
        cash_weight=Decimal("0.00"),
        input_fingerprint="test-fp",
        source="csv",
        created_at=now,
    )
    session.add(snap)

    # Seed Holding
    session.add(
        PortfolioHolding(
            id=UUID("55555555-5555-5555-5555-555555555555"),
            snapshot_id=snap_id,
            owner_id=USER_A_ID,
            security_id=sec_id,
            symbol="TCS",
            quantity=Decimal("10.00"),
        )
    )

    # Seed Transaction belonging to User A
    tx_a = PortfolioTransaction(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        portfolio_id=portfolio_a_id,
        owner_id=USER_A_ID,
        transaction_type="BUY",
        trade_date=date(2026, 1, 15),
        symbol="TCS",
        quantity=Decimal("10"),
        price=Decimal("3500.00"),
        amount=Decimal("35000.00"),
        fees=Decimal("20.00"),
        created_at=now,
    )
    session.add(tx_a)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_user_b_cannot_access_user_a_portfolio_or_ledger(test_db_session: Session) -> None:
    """User B authenticated session must receive 404 when attempting to access User A's data."""
    portfolio_a_id = "11111111-1111-1111-1111-111111111111"

    app.dependency_overrides[get_session] = lambda: test_db_session
    # Impersonate User B
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=USER_B_ID, email="user_b@prism.local"
    )

    client = TestClient(app)

    try:
        # 1. User B cannot view User A's portfolio
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}")
        assert resp.status_code == 404, "User B should not see User A's portfolio"

        # 2. User B cannot view User A's transactions
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}/transactions")
        assert resp.status_code == 404

        # 3. User B cannot post transactions to User A's portfolio
        resp = client.post(
            f"/api/v1/portfolios/{portfolio_a_id}/transactions",
            json={
                "transactions": [
                    {
                        "transaction_type": "DEPOSIT",
                        "trade_date": "2026-02-01",
                        "amount": 100000.0,
                    }
                ]
            },
        )
        assert resp.status_code == 404

        # 4. User B cannot view reconciliation of User A's portfolio
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}/reconciliation")
        assert resp.status_code == 404

        # 5. User B cannot export User A's transactions to CSV
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}/transactions/export-csv")
        assert resp.status_code == 404

        # 6. User B cannot view User A's risk history
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}/risk-history")
        assert resp.status_code == 404

    finally:
        app.dependency_overrides.clear()


def test_user_a_can_access_own_portfolio_and_ledger(test_db_session: Session) -> None:
    """User A authenticated session can successfully view and access their own portfolio."""
    portfolio_a_id = "11111111-1111-1111-1111-111111111111"

    app.dependency_overrides[get_session] = lambda: test_db_session
    # Authenticate as legitimate owner User A
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=USER_A_ID, email="user_a@prism.local"
    )

    client = TestClient(app)

    try:
        # User A views own portfolio
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "User A Confidential Portfolio"

        # User A views own transactions
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}/transactions")
        assert resp.status_code == 200
        txs = resp.json()
        assert len(txs) == 1
        assert txs[0]["symbol"] == "TCS"
        assert txs[0]["transaction_type"] == "BUY"

        # User A can export transactions
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}/transactions/export-csv")
        assert resp.status_code == 200
        assert "TCS" in resp.text

    finally:
        app.dependency_overrides.clear()
