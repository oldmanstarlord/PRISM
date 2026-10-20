"""Small dependency-free HTTP hardening helpers for the PRISM API."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.config import Settings

logger = logging.getLogger("prism.http")


class SlidingWindowRateLimiter:
    """Process-local limiter for costly endpoints.

    This protects a single API process from accidental or low-volume abuse. A shared
    gateway/Redis limiter is still required when PRISM is deployed with multiple workers.
    """

    def __init__(self, requests: int, window_seconds: int) -> None:
        self.requests = requests
        self.window_seconds = window_seconds
        self._events: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, int]:
        timestamp = now if now is not None else time.monotonic()
        cutoff = timestamp - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.requests:
                retry_after = max(1, int(self.window_seconds - (timestamp - events[0])))
                return False, retry_after
            events.append(timestamp)
            return True, 0


class SecurityMiddleware(BaseHTTPMiddleware):
    """Apply request limits, timeouts, safe headers, and metadata-only access logs."""

    def __init__(self, app: object, *, settings: Settings) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.settings = settings
        self.limiter = SlidingWindowRateLimiter(
            settings.expensive_rate_limit_requests,
            settings.expensive_rate_limit_window_seconds,
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))[:64]
        started = time.perf_counter()

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.settings.max_request_bytes:
                    return self._finalize(
                        JSONResponse(
                            status_code=413,
                            content={"detail": "Request body exceeds the configured size limit"},
                        ),
                        request_id,
                    )
            except ValueError:
                return self._finalize(
                    JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"}),
                    request_id,
                )

        if self._is_expensive(request.url.path):
            client = request.client.host if request.client else "unknown"
            allowed, retry_after = self.limiter.allow(f"{client}:{request.url.path}")
            if not allowed:
                limited_response = JSONResponse(
                    status_code=429,
                    content={"detail": "Request rate limit exceeded; retry later"},
                )
                limited_response.headers["Retry-After"] = str(retry_after)
                return self._finalize(limited_response, request_id)

        response: Response
        try:
            response = await asyncio.wait_for(
                call_next(request), timeout=self.settings.request_timeout_seconds
            )
        except TimeoutError:
            logger.warning(
                json.dumps(
                    {
                        "event": "request_timeout",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                    }
                )
            )
            response = JSONResponse(
                status_code=504,
                content={"detail": "Request timed out before completion"},
            )

        response = self._finalize(response, request_id)
        logger.info(
            json.dumps(
                {
                    "event": "request_complete",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                }
            )
        )
        return response

    def _is_expensive(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in self.settings.expensive_path_prefixes)

    def _finalize(self, response: Response, request_id: str) -> Response:
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response
