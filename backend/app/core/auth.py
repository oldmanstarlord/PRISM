"""Shared portfolio identity; legacy token verification for provisioning scripts only."""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi import status as http_status

from backend.app.core.config import settings



@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str | None


def verify_access_token(token: str) -> AuthenticatedUser:
    """Verify a Supabase JWT through the Auth server, including legacy HS256 projects."""
    if token.startswith("local."):
        from backend.app.core.local_accounts import verify

        user_id, email = verify(token)
        return AuthenticatedUser(id=user_id, email=email)
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured",
        )
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/user"
    try:
        response = httpx.get(
            url,
            headers={
                "apikey": settings.supabase_publishable_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=5.0,
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc
    if response.status_code != http_status.HTTP_200_OK:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload: Any = response.json()
    try:
        user_id = UUID(str(payload["id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication response did not contain a valid user",
        ) from exc
    email = payload.get("email")
    return AuthenticatedUser(id=user_id, email=email if isinstance(email, str) else None)


def require_user() -> AuthenticatedUser:
    """Resolve the shared Aarav portfolio owner; this deployment has no login."""
    from sqlalchemy import select
    from backend.app.db.models import Portfolio
    from backend.app.db.session import SessionLocal

    with SessionLocal() as session:
        owner = session.scalar(
            select(Portfolio.owner_id)
            .where(Portfolio.name == "Aarav's Portfolio", Portfolio.owner_id.is_not(None))
            .order_by(Portfolio.updated_at.desc())
            .limit(1)
        )
    return AuthenticatedUser(
        id=owner or UUID("00000000-0000-0000-0000-000000000101"),
        email=None,
    )


CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]
