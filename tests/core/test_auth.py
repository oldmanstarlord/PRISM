from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException

from backend.app.core import auth


def test_verify_access_token_returns_supabase_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(auth.settings, "supabase_publishable_key", "public-key")

    def fake_get(url: str, *, headers: dict[str, str], timeout: float) -> httpx.Response:
        assert url == "https://example.supabase.co/auth/v1/user"
        assert headers["Authorization"] == "Bearer valid-token"
        assert headers["apikey"] == "public-key"
        assert timeout == 5.0
        return httpx.Response(
            200,
            json={"id": "00000000-0000-0000-0000-000000000123", "email": "user@example.com"},
        )

    monkeypatch.setattr(auth.httpx, "get", fake_get)
    user = auth.verify_access_token("valid-token")

    assert user.id == UUID("00000000-0000-0000-0000-000000000123")
    assert user.email == "user@example.com"


def test_verify_access_token_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setattr(auth.settings, "supabase_publishable_key", "public-key")
    monkeypatch.setattr(auth.httpx, "get", lambda *args, **kwargs: httpx.Response(401))

    with pytest.raises(HTTPException) as error:
        auth.verify_access_token("bad-token")

    assert error.value.status_code == 401


@pytest.mark.parametrize("owner", [None, UUID("12345678-1234-5678-1234-567812345678")])
def test_shared_portfolio_requires_no_token_and_preserves_owner(monkeypatch, owner):
    from contextlib import nullcontext
    from unittest.mock import Mock
    from backend.app.db import session as db_session
    session = Mock()
    session.scalar.return_value = owner
    monkeypatch.setattr(db_session, "SessionLocal", lambda: nullcontext(session))
    user = auth.require_user()
    assert user.id == (owner or UUID("00000000-0000-0000-0000-000000000101"))
    assert user.email is None
    query = str(session.scalar.call_args.args[0])
    assert "portfolio.name" in query
    assert "owner_id IS NOT NULL" in query
