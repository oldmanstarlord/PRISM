from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

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


def test_require_user_uses_fixed_identity_in_local_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth.settings, "environment", "development")
    monkeypatch.setattr(auth.settings, "local_auth_enabled", True)

    user = auth.require_user(None)

    assert user.id == auth.LOCAL_DEVELOPMENT_USER_ID
    assert user.email == "local-development@prism.invalid"


def test_require_user_does_not_bypass_invalid_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth.settings, "environment", "development")
    monkeypatch.setattr(auth.settings, "local_auth_enabled", True)
    monkeypatch.setattr(
        auth,
        "verify_access_token",
        lambda _token: (_ for _ in ()).throw(HTTPException(status_code=401)),
    )

    with pytest.raises(HTTPException) as error:
        auth.require_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid"))

    assert error.value.status_code == 401
