import json
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.v1.router import router as v1_router
from backend.app.core.config import settings
from backend.app.core.security import SecurityMiddleware

logger = logging.getLogger("prism.error")

app = FastAPI(
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
