"""Middleware for rate limit headers and request logging with trace IDs."""

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger()


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """Adds X-RateLimit-* headers to authenticated responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        rate_limit = getattr(request.state, "rate_limit", None)
        if rate_limit is not None:
            response.headers["X-RateLimit-Limit"] = str(rate_limit.limit)
            response.headers["X-RateLimit-Remaining"] = str(rate_limit.remaining)
            response.headers["X-RateLimit-Reset"] = str(rate_limit.reset)

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Generates trace_id per request, logs method/path/status/duration, returns X-Trace-Id header."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        trace_id = uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start_time) * 1000, 1)

        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Trace-Id"] = trace_id
        structlog.contextvars.unbind_contextvars("trace_id")

        return response
