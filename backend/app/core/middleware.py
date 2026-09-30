"""Request-scoped correlation context."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.error_catalog import PUBLIC_ERRORS
from app.core.logging import request_id_context


REQUEST_ID_HEADER = "X-Request-Id"
MAX_REQUEST_ID_LENGTH = 36
error_logger = logging.getLogger("app.errors")


def valid_request_id(value: str | None) -> str | None:
    """Accept only the canonical, bounded text form of a UUID."""

    if not value or len(value) > MAX_REQUEST_ID_LENGTH:
        return None
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return None
    canonical = str(parsed)
    return canonical if value == canonical else None


def request_id_for(request) -> str:
    return getattr(request.state, "request_id", "")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = valid_request_id(request.headers.get(REQUEST_ID_HEADER))
        if request_id is None:
            request_id = str(uuid4())
        request.state.request_id = request_id
        token = request_id_context.set(request_id)
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            request_id_context.reset(token)


class SafeExceptionMiddleware(BaseHTTPMiddleware):
    """Convert unexpected route failures without retaining raw exception secrets."""

    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = request_id_for(request)
            # Alembic's in-process fileConfig may disable pre-existing loggers.
            error_logger.disabled = False
            error_logger.error(
                "unhandled_request_error",
                extra={
                    "request_id": request_id,
                    "exception_type": type(exc).__name__,
                },
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": PUBLIC_ERRORS["INTERNAL_ERROR"],
                        "request_id": request_id,
                    }
                },
            )
