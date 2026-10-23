"""Supabase access-token verification for protected API routes."""

from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException
from fastapi import status as http_status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)
LOCAL_DEVELOPMENT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str | None


def verify_access_token(token: str) -> AuthenticatedUser:
    """Verify a Supabase JWT through the Auth server, including legacy HS256 projects."""
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


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        if settings.local_auth_enabled and settings.environment.lower() == "development":
            return AuthenticatedUser(
                id=LOCAL_DEVELOPMENT_USER_ID,
                email="local-development@prism.invalid",
            )
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_access_token(credentials.credentials)


CurrentUser = Annotated[AuthenticatedUser, Depends(require_user)]
