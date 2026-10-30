import pytest
from fastapi import HTTPException

from backend.app.core import auth, local_accounts


@pytest.fixture(autouse=True)
def local_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(local_accounts.settings, "environment", "development")
    monkeypatch.setattr(local_accounts.settings, "local_auth_enabled", True)
    monkeypatch.setenv("PRISM_LOCAL_ACCOUNT_PASSWORD", "test-password")


def test_accounts_receive_distinct_verified_identities() -> None:
    identities = set()
    for email in local_accounts.ACCOUNTS:
        token, _ = local_accounts.authenticate(email, "test-password")
        user = auth.verify_access_token(token)
        assert user.email == email
        identities.add(user.id)
    assert len(identities) == 3


def test_wrong_password_and_unknown_account_are_rejected() -> None:
    for email, password in [("aarav@prism.com", "wrong"), ("unknown@prism.com", "test-password")]:
        with pytest.raises(HTTPException) as error:
            local_accounts.authenticate(email, password)
        assert error.value.status_code == 401


def test_tampered_and_expired_tokens_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    token, expires = local_accounts.authenticate("aarav@prism.com", "test-password")
    with pytest.raises(HTTPException):
        local_accounts.verify(token.replace("000101", "000102"))
    monkeypatch.setattr(local_accounts.time, "time", lambda: expires + 1)
    with pytest.raises(HTTPException):
        local_accounts.verify(token)


def test_local_tokens_cannot_be_used_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    token, _ = local_accounts.authenticate("aarav@prism.com", "test-password")
    monkeypatch.setattr(local_accounts.settings, "local_auth_enabled", False)
    with pytest.raises(HTTPException):
        local_accounts.verify(token)
    with pytest.raises(HTTPException):
        local_accounts.authenticate("aarav@prism.com", "test-password")
