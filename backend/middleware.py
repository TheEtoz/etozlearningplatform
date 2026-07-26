"""HTTP middleware for security headers and simple rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline browser security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        if not settings.debug:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window rate limiter keyed by client IP + route class."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _limit_for_path(self, path: str) -> int:
        if path.startswith("/api/v1/auth/"):
            return settings.auth_rate_limit_per_minute
        if path.startswith("/api/v1/code/") or path == "/api/v1/submissions":
            # Code execution is expensive — keep this tighter.
            return min(settings.rate_limit_per_minute, 30)
        return settings.rate_limit_per_minute

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)

        # Local/dev and pytest use DEBUG=True — keep limits for production only.
        if settings.debug:
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        limit = self._limit_for_path(path)
        key = f"{self._client_ip(request)}:{path.split('/')[3] if path.count('/') >= 3 else path}"
        now = time.monotonic()
        window_start = now - 60.0

        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            "Too many requests. Please wait a minute and try again."
                        )
                    },
                    headers={"Retry-After": "60"},
                )
            bucket.append(now)

        return await call_next(request)
