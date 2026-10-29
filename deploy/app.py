"""Single-origin production host for the built UI and the existing API."""

import os
from pathlib import Path

from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.app.core.config import settings
from backend.app.main import app as api


class FrontendFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            # Preserve missing API/asset errors; only client routes use the SPA shell.
            if exc.status_code != 404 or path.startswith(("api/", "assets/")) or "." in path:
                raise
            response = FileResponse(Path(str(self.directory)) / "index.html")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        )
        return response


class ProductionApp:
    def __init__(self, api_app: ASGIApp, directory: str) -> None:
        self.api = api_app
        self.frontend = FrontendFiles(directory=directory, html=True)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or path in {"/health", "/api"} or path.startswith("/api/"):
            await self.api(scope, receive, send)
        else:
            try:
                await self.frontend(scope, receive, send)
            except HTTPException as exc:
                await Response(status_code=exc.status_code)(scope, receive, send)


app = TrustedHostMiddleware(
    ProductionApp(api, os.getenv("PRISM_FRONTEND_DIR", "/app/frontend/dist")),
    allowed_hosts=settings.trusted_hosts,
)
