"""Read cached news; authorize and queue bounded paid refreshes."""

from functools import lru_cache
from ipaddress import ip_address
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict

from backend.app.core.auth import bearer_scheme, require_user
from backend.app.core.config import settings
from backend.app.news.collection import NewsService
from backend.app.news.provider import ProviderError
from backend.app.news.sentiment import ModelUnavailable
from backend.app.news.store import RefreshBlocked

router = APIRouter(prefix="/news", tags=["news intelligence"])


@lru_cache
def get_news_service() -> NewsService:
    return NewsService(settings)


def authorize_refresh(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> None:
    # Local development only. Do not trust X-Forwarded-For or arbitrary Host/Origin headers.
    origin = request.headers.get("origin")
    host = request.url.hostname
    try:
        local = bool(request.client and ip_address(request.client.host).is_loopback)
    except ValueError:
        local = False
    if (
        settings.environment == "development"
        and local
        and host in {"localhost", "127.0.0.1", "::1"}
        and (origin is None or origin in settings.cors_origins)
    ):
        return
    require_user(credentials)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.get("")
def news_feed(
    symbol: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9&.-]{1,30}$")] = None,
) -> dict[str, Any]:
    return get_news_service().feed(symbol)


@router.post("/refresh", status_code=202, dependencies=[Depends(authorize_refresh)])
def refresh_news(body: RefreshRequest, tasks: BackgroundTasks) -> dict[str, str]:
    service = get_news_service()
    try:
        token = service.prepare()
    except (ProviderError, ModelUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RefreshBlocked as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    tasks.add_task(service.collect, token)
    return {"status": "started"}
