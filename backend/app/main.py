# mypy: disable-error-code=import-untyped

import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.v1.router import router as v1_router
from backend.app.core.config import settings
from backend.app.core.security import SecurityMiddleware
from backend.app.news.collection_router import get_news_service
from backend.app.news.publication_window import NEWS_TIMEZONE

logger = logging.getLogger("prism.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    scheduler = None
    if settings.news_auto_refresh or settings.gnn_auto_refresh:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(timezone=NEWS_TIMEZONE)

        def collect_news() -> None:
            try:
                service = get_news_service()
                if service.status()["can_refresh"]:
                    service.collect_in_worker(service.prepare())
            except Exception:
                logger.warning("Scheduled news refresh was skipped")

        if settings.news_auto_refresh:
            scheduler.add_job(
                collect_news,
                "interval",
                minutes=settings.news_refresh_minutes,
                max_instances=1,
                coalesce=True,
                next_run_time=datetime.now(UTC),
            )
            scheduler.add_job(
                collect_news,
                "cron",
                hour=0,
                minute=0,
                max_instances=1,
                coalesce=True,
            )
        if settings.gnn_auto_refresh:
            from jobs.run_weekly_gnn import run as run_weekly_gnn

            def refresh_gnn() -> None:
                try:
                    assert settings.gnn_run_path is not None
                    assert settings.gnn_calibration_path is not None
                    run_weekly_gnn(
                        settings.gnn_history_start,
                        settings.gnn_run_path,
                        settings.gnn_calibration_path,
                    )
                except Exception:
                    logger.exception("Scheduled GNN refresh failed")

            scheduler.add_job(
                refresh_gnn,
                "cron",
                day_of_week="sat",
                hour=8,
                minute=0,
                max_instances=1,
                coalesce=True,
            )
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    lifespan=lifespan,
    title="PRISM API",
    version="0.1.0",
    description="Portfolio Risk & Intelligence System for Markets",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(SecurityMiddleware, settings=settings)
app.include_router(v1_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    request_id = request.headers.get("x-request-id", "unassigned")[:64]
    logger.error(
        json.dumps(
            {
                "event": "unhandled_exception",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "exception_type": type(exc).__name__,
            }
        )
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "prism-api"}
