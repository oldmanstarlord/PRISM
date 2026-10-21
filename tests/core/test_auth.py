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
