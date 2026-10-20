"""Step 4 Multi-User Persistence, Authorization, and Idempotency tests."""

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
    PortfolioRiskHistory,
    PortfolioSnapshot,
    PortfolioTransaction,
    Security,
)
from backend.app.db.session import get_session
from backend.app.main import app

USER_A_ID = UUID("00000000-0000-0000-0000-000000000001")
USER_B_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def multi_user_db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    now = datetime.now(UTC)

    # Seed Securities
    sec_tcs = Security(
        id=UUID("33333333-3333-3333-3333-333333333331"),
        isin="INE467B01029",
        company_name="TCS",
        currency="INR",
        is_active=True,
    )
    sec_infy = Security(
        id=UUID("33333333-3333-3333-3333-333333333332"),
        isin="INE009A01021",
        company_name="INFY",
        currency="INR",
        is_active=True,
    )
    session.add_all([sec_tcs, sec_infy])

    # Seed Portfolio exclusively for User A
    portfolio_a_id = UUID("11111111-1111-1111-1111-111111111111")
    portfolio_a = Portfolio(
        id=portfolio_a_id,
        owner_id=USER_A_ID,
        owner_ref="user-a",
        name="User A Portfolio",
        input_mode="quantities",
        currency="INR",
        created_at=now,
        updated_at=now,
    )
    session.add(portfolio_a)

    snap_id = UUID("44444444-4444-4444-4444-444444444444")
    snap = PortfolioSnapshot(
        id=snap_id,
        portfolio_id=portfolio_a_id,
        owner_id=USER_A_ID,
        valuation_date=date(2026, 1, 15),
        cash_amount=Decimal("50000.00"),
        cash_weight=Decimal("0.00"),
        input_fingerprint="fp-a",
        source="csv",
        created_at=now,
    )
    session.add(snap)

    session.add(
        PortfolioHolding(
            id=UUID("55555555-5555-5555-5555-555555555555"),
            snapshot_id=snap_id,
            owner_id=USER_A_ID,
            security_id=sec_tcs.id,
            symbol="TCS",
            quantity=Decimal("10.00"),
        )
    )

    session.add(
        PortfolioTransaction(
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
            idempotency_key="tx-init-tcs",
            created_at=now,
        )
    )

    # Pre-seed a Risk History record for User A
    session.add(
        PortfolioRiskHistory(
            id=UUID("66666666-6666-6666-6666-666666666666"),
            portfolio_id=portfolio_a_id,
            owner_id=USER_A_ID,
            snapshot_id=snap_id,
            valuation_date=date(2026, 1, 15),
            portfolio_risk_score=Decimal("41.25"),
            portfolio_classification="Moderate Risk",
            annualized_volatility=Decimal("0.1650"),
            downside_volatility=Decimal("0.1120"),
            max_drawdown=Decimal("0.0850"),
            diversification_score=Decimal("65.00"),
            effective_holdings=Decimal("1.00"),
            top_sector="Information Technology",
            top_sector_weight=Decimal("100.00"),
            largest_holding="TCS",
            largest_holding_weight=Decimal("100.00"),
            indicators_summary={"indicators_count": 5},
            methodology_version="1.0.0",
            data_cutoff=date(2026, 1, 14),
            computed_at=now,
        )
    )

    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_ensure_active_portfolio_creates_and_idempotent(multi_user_db_session: Session) -> None:
    """POST /portfolios/ensure-active creates initial portfolio if none, returns existing if present."""
    app.dependency_overrides[get_session] = lambda: multi_user_db_session
    # Authenticate as User B who has no portfolio initially
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=USER_B_ID, email="user_b@prism.local"
    )
    client = TestClient(app)

    try:
        # First call: should create primary portfolio for User B
        resp = client.post(
            "/api/v1/portfolios/ensure-active",
            json={
                "name": "User B Primary Portfolio",
                "input_mode": "quantities",
                "initial_holdings": [
                    {"symbol": "INFY", "quantity": 15, "buy_price": 1800.0},
                ],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["owner_id"] == str(USER_B_ID)
        assert data["name"] == "User B Primary Portfolio"
        portfolio_b_id = data["id"]
        assert len(data["holdings"]) == 1
        assert data["holdings"][0]["symbol"] == "INFY"

        # Second call: must return existing portfolio and not duplicate it
        resp2 = client.post(
            "/api/v1/portfolios/ensure-active",
            json={"name": "User B Second Call", "initial_holdings": []},
        )
        assert resp2.status_code == 200
        assert resp2.json()["id"] == portfolio_b_id
        assert resp2.json()["name"] == "User B Primary Portfolio"

        # Verify User B transactions contain the initial BUY
        tx_resp = client.get(f"/api/v1/portfolios/{portfolio_b_id}/transactions")
        assert tx_resp.status_code == 200
        txs = tx_resp.json()
        assert len(txs) == 1
        assert txs[0]["symbol"] == "INFY"
        assert txs[0]["transaction_type"] == "BUY"

    finally:
        app.dependency_overrides.clear()


def test_transaction_idempotency_prevents_duplicate_submission(
    multi_user_db_session: Session,
) -> None:
    """Submitting transactions with an idempotency_key does not duplicate ledger records on retry."""
    portfolio_a_id = "11111111-1111-1111-1111-111111111111"

    app.dependency_overrides[get_session] = lambda: multi_user_db_session
    app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
        id=USER_A_ID, email="user_a@prism.local"
    )
    client = TestClient(app)

    try:
        # Initial transaction count for User A
        tx_list_1 = client.get(f"/api/v1/portfolios/{portfolio_a_id}/transactions").json()
        initial_count = len(tx_list_1)
        assert initial_count == 1

        payload = {
            "transactions": [
                {
                    "transaction_type": "BUY",
                    "trade_date": "2026-02-01",
                    "symbol": "INFY",
                    "quantity": 20,
                    "price": 1850.0,
                    "idempotency_key": "unique-client-tx-key-101",
                }
            ]
        }

        # First attempt: successfully records
        resp1 = client.post(f"/api/v1/portfolios/{portfolio_a_id}/transactions", json=payload)
        assert resp1.status_code == 201
        created_tx = resp1.json()[0]
        assert created_tx["symbol"] == "INFY"
        assert created_tx["idempotency_key"] == "unique-client-tx-key-101"

        # Check count increased by 1
        tx_list_2 = client.get(f"/api/v1/portfolios/{portfolio_a_id}/transactions").json()
        assert len(tx_list_2) == initial_count + 1

        # Second attempt (simulating client retry / network timeout retry)
        resp2 = client.post(f"/api/v1/portfolios/{portfolio_a_id}/transactions", json=payload)
        assert resp2.status_code == 201
        retried_tx = resp2.json()[0]

        # Must return the SAME transaction id without inserting a duplicate
        assert retried_tx["id"] == created_tx["id"]

        # Check total count did NOT increase
        tx_list_3 = client.get(f"/api/v1/portfolios/{portfolio_a_id}/transactions").json()
        assert len(tx_list_3) == initial_count + 1

    finally:
        app.dependency_overrides.clear()


def test_risk_history_snapshots_persistence_and_isolation(
    multi_user_db_session: Session,
) -> None:
    """Portfolio risk history records methodology version, calculation date, cutoff, and enforces isolation."""
    portfolio_a_id = "11111111-1111-1111-1111-111111111111"

    app.dependency_overrides[get_session] = lambda: multi_user_db_session

    client = TestClient(app)

    try:
        # 1. User B tries to save a risk snapshot to User A's portfolio -> 404
        app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
            id=USER_B_ID, email="user_b@prism.local"
        )
        resp = client.post(
            f"/api/v1/portfolios/{portfolio_a_id}/risk-history",
            json={
                "valuation_date": "2026-02-15",
                "portfolio_risk_score": 45.0,
                "portfolio_classification": "Moderate Risk",
                "annualized_volatility": 0.175,
                "downside_volatility": 0.12,
                "max_drawdown": 0.09,
                "diversification_score": 70.0,
                "effective_holdings": 2.0,
                "top_sector": "IT",
                "top_sector_weight": 60.0,
                "largest_holding": "TCS",
                "largest_holding_weight": 60.0,
                "methodology_version": "1.0.0",
                "data_cutoff": "2026-02-14",
            },
        )
        assert resp.status_code == 404

        # 2. User A saves a risk snapshot to own portfolio -> 201
        app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
            id=USER_A_ID, email="user_a@prism.local"
        )
        resp = client.post(
            f"/api/v1/portfolios/{portfolio_a_id}/risk-history",
            json={
                "valuation_date": "2026-02-15",
                "portfolio_risk_score": 45.0,
                "portfolio_classification": "Moderate Risk",
                "annualized_volatility": 0.175,
                "downside_volatility": 0.12,
                "max_drawdown": 0.09,
                "diversification_score": 70.0,
                "effective_holdings": 2.0,
                "top_sector": "IT",
                "top_sector_weight": 60.0,
                "largest_holding": "TCS",
                "largest_holding_weight": 60.0,
                "methodology_version": "1.0.0",
                "data_cutoff": "2026-02-14",
            },
        )
        assert resp.status_code == 201
        saved = resp.json()
        assert saved["methodology_version"] == "1.0.0"
        assert saved["data_cutoff"] == "2026-02-14"
        assert saved["valuation_date"] == "2026-02-15"

        # 3. User A lists risk history -> both snapshots exist (historical preservation)
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}/risk-history")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 2
        assert history[0]["valuation_date"] == "2026-01-15"
        assert history[1]["valuation_date"] == "2026-02-15"

        # 4. User B cannot view User A's risk history -> 404
        app.dependency_overrides[require_user] = lambda: AuthenticatedUser(
            id=USER_B_ID, email="user_b@prism.local"
        )
        resp = client.get(f"/api/v1/portfolios/{portfolio_a_id}/risk-history")
        assert resp.status_code == 404

    finally:
        app.dependency_overrides.clear()
