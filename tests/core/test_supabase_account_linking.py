from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.core import local_accounts, login_router
from backend.app.db.models import Base, Portfolio, PortfolioTransaction
from jobs import link_supabase_accounts


def test_linking_preserves_holdings_and_isolates_new_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_accounts.settings, "environment", "development")
    monkeypatch.setattr(local_accounts.settings, "local_auth_enabled", True)
    monkeypatch.setenv("PRISM_LOCAL_ACCOUNT_PASSWORD", "test-password")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(login_router, "SessionLocal", factory)
    monkeypatch.setattr(link_supabase_accounts, "SessionLocal", factory)
    new_id = UUID("10000000-0000-0000-0000-000000000101")
    try:
        for email in ["aarav@prism.com", "priya@prism.com"]:
            login_router.login(login_router.LoginRequest(email=email, password="test-password"))
        with factory() as session:
            original = session.scalar(
                select(Portfolio).where(Portfolio.name == "Aarav's Portfolio")
            )
            assert original is not None
            original_id = original.id
            original.name = "Saved custom portfolio"
            session.commit()
        link_supabase_accounts.link_account("aarav@prism.com", new_id)
        link_supabase_accounts.link_account("aarav@prism.com", new_id)
        with factory() as session:
            portfolio = session.get(Portfolio, original_id)
            assert portfolio is not None
            assert portfolio.owner_id == new_id
            assert portfolio.name == "Saved custom portfolio"
            transactions = session.scalars(
                select(PortfolioTransaction).where(
                    PortfolioTransaction.owner_id == new_id,
                )
            ).all()
            assert len(transactions) == 5
            assert {tx.symbol for tx in transactions} == {
                "HDFCBANK",
                "ITC",
                "HINDUNILVR",
                "TCS",
                "SUNPHARMA",
            }
            for table in Base.metadata.sorted_tables:
                if "owner_id" in table.c:
                    assert (
                        session.execute(
                            select(table).where(
                                table.c.owner_id
                                == UUID(local_accounts.ACCOUNTS["aarav@prism.com"][0]),
                            )
                        ).first()
                        is None
                    )
            priya = session.scalar(select(Portfolio).where(Portfolio.name == "Priya's Portfolio"))
            assert priya is not None
            assert priya.owner_id == UUID(local_accounts.ACCOUNTS["priya@prism.com"][0])
    finally:
        engine.dispose()
