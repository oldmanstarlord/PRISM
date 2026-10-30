"""Fixed local presentation accounts; unavailable outside development."""

import hashlib
import hmac
import os
import secrets
import time
from uuid import UUID

from fastapi import HTTPException

from backend.app.core.config import settings

ACCOUNTS = {
    "aarav@prism.com": (
        "00000000-0000-0000-0000-000000000101",
        "Aarav",
        [
            ("HDFCBANK", 100, 1650),
            ("ITC", 200, 420),
            ("HINDUNILVR", 40, 2400),
            ("TCS", 25, 3800),
            ("SUNPHARMA", 50, 1700),
        ],
    ),
    "priya@prism.com": (
        "00000000-0000-0000-0000-000000000102",
        "Priya",
        [
            ("RELIANCE", 80, 1400),
            ("INFY", 70, 1750),
            ("ICICIBANK", 100, 1200),
            ("LT", 30, 3400),
            ("MARUTI", 10, 11500),
        ],
    ),
    "rohan@prism.com": (
        "00000000-0000-0000-0000-000000000103",
        "Rohan",
        [
            ("TATAMOTORS", 150, 750),
            ("BAJFINANCE", 30, 7000),
            ("ADANIENT", 40, 2500),
            ("TATASTEEL", 500, 150),
            ("BEL", 300, 280),
        ],
    ),
}
_SIGNING_KEY = os.environ.get("PRISM_LOCAL_AUTH_SECRET") or secrets.token_hex(32)


def enabled() -> bool:
    return settings.local_auth_enabled and settings.environment.lower() == "development"


def authenticate(email: str, password: str) -> tuple[str, int]:
    if not enabled():
        raise HTTPException(404, "Login unavailable")
    expected = os.environ.get("PRISM_LOCAL_ACCOUNT_PASSWORD", "Prism@2026")
    if not hmac.compare_digest(password.encode(), expected.encode()) or email not in ACCOUNTS:
        raise HTTPException(401, "Incorrect email or password")
    expires = int(time.time()) + 8 * 60 * 60
    payload = f"{ACCOUNTS[email][0]}.{expires}"
    signature = hmac.new(_SIGNING_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"local.{payload}.{signature}", expires


def verify(token: str) -> tuple[UUID, str]:
    try:
        prefix, user_id, expiry, signature = token.split(".")
        payload = f"{user_id}.{expiry}"
        expected = hmac.new(_SIGNING_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not enabled() or prefix != "local" or not hmac.compare_digest(signature, expected):
            raise ValueError
        if int(expiry) <= time.time():
            raise ValueError
        email = next(email for email, account in ACCOUNTS.items() if account[0] == user_id)
        return UUID(user_id), email
    except (ValueError, StopIteration) as exc:
        raise HTTPException(401, "Session expired. Please sign in again") from exc
