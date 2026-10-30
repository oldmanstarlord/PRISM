from contextlib import nullcontext
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.core import local_accounts, login_router
from backend.app.db.models import Base, Portfolio, PortfolioTransaction


def test_login_seeds_only_authenticated_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_accounts.settings, "environment", "development")
    monkeypatch.setattr(local_accounts.settings, "local_auth_enabled", True)
    monkeypatch.setenv("PRISM_LOCAL_ACCOUNT_PASSWORD", "test-password")
    session = object()
    monkeypatch.setattr(login_router, "SessionLocal", lambda: nullcontext(session))
    seed = Mock()
    monkeypatch.setattr(login_router, "ensure_active_portfolio", seed)

    response = login_router.login(
        login_router.LoginRequest(
            email=" PRIYA@PRISM.COM ",
            password="test-password",
        )
    )
    request, actual_session, user = seed.call_args.args
    assert actual_session is session
    assert user.email == "priya@prism.com"
    assert request.name == "Priya's Portfolio"
    assert {h.symbol for h in request.initial_holdings} == {
        "RELIANCE",
        "INFY",
        "ICICIBANK",
        "LT",
        "MARUTI",
    }
    assert response["user"]["id"] == str(user.id)

    seed.reset_mock()
    with pytest.raises(HTTPException):
        login_router.login(login_router.LoginRequest(email="priya@prism.com", password="wrong"))
    seed.assert_not_called()


def test_first_login_seeds_separate_portfolios_and_repeat_login_preserves_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_accounts.settings, "environment", "development")
    monkeypatch.setattr(local_accounts.settings, "local_auth_enabled", True)
    monkeypatch.setenv("PRISM_LOCAL_ACCOUNT_PASSWORD", "test-password")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(login_router, "SessionLocal", factory)
    try:
        for email in local_accounts.ACCOUNTS:
            login_router.login(login_router.LoginRequest(email=email, password="test-password"))
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Portfolio)) == 3
            assert session.scalar(select(func.count()).select_from(PortfolioTransaction)) == 15
            portfolio = session.scalar(
                select(Portfolio).where(Portfolio.name == "Priya's Portfolio")
            )
            assert portfolio is not None
            portfolio.name = "Priya's saved changes"
            session.commit()
        login_router.login(
            login_router.LoginRequest(
                email="priya@prism.com",
                password="test-password",
            )
        )
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(Portfolio)) == 3
            assert session.scalar(select(func.count()).select_from(PortfolioTransaction)) == 15
            assert (
                session.scalar(
                    select(Portfolio).where(
                        Portfolio.name == "Priya's saved changes",
                    )
                )
                is not None
            )
    finally:
        engine.dispose()
