"""Untrusted webhook trigger: it can only make an authoritative poll due."""

from __future__ import annotations

import hashlib
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.error_catalog import PUBLIC_ERRORS
from app.core.time_utils import utc_now
from app.api.v1.dependencies import APIProblem
from app.core.middleware import request_id_for
from app.core.rate_limit import BoundedSlidingWindowLimiter, trusted_remote_key
from app.models import IngestionCursor


router = APIRouter()
_MAX_BODY_BYTES = 64 * 1024
_RATE_LIMIT = 10
_RATE_WINDOW_SECONDS = 60.0
_MAX_RATE_BUCKETS = 4096
_rate_limiter = BoundedSlidingWindowLimiter(
    calls_per_period=_RATE_LIMIT,
    period_seconds=int(_RATE_WINDOW_SECONDS),
    max_buckets=_MAX_RATE_BUCKETS,
)
_requests = _rate_limiter.requests


def _payload_too_large() -> APIProblem:
    return APIProblem(
        413,
        "PAYLOAD_TOO_LARGE",
        "Размер запроса превышает 64 КиБ.",
    )


def reset_webhook_rate_limits() -> None:
    _rate_limiter.reset()


def _limited(key: str, now: float) -> bool:
    limited, _ = _rate_limiter.check(key, now=now)
    return limited


async def _body_within_limit(request: Request, limit: int) -> bool:
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            return False
    return True


@router.post("/amocrm/{hook_id}", status_code=202)
async def amocrm_webhook(hook_id: str, request: Request, db: Session = Depends(get_db)):
    """Accept an opaque trigger and schedule only an authoritative API poll.

    amoCRM does not provide a documented request-signature header for this
    callback. The 256-bit opaque path is therefore the provider-compatible
    authenticity control. Only its SHA-256 digest is queried from storage.
    Known and unknown paths share body parsing, remote limiting, one indexed
    lookup and the same 202 response; only a known path may make polling due.
    """
    request.state.ingress_guarded = True
    hook_hash = hashlib.sha256(hook_id.encode()).hexdigest()
    remote = trusted_remote_key(request)
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BODY_BYTES:
                raise _payload_too_large()
        except ValueError:
            raise _payload_too_large()
    if not await _body_within_limit(request, _MAX_BODY_BYTES):
        raise _payload_too_large()
    # One bounded bucket per socket peer prevents random unknown IDs from growing
    # memory. Browser-controlled proxy headers are deliberately ignored.
    rate_key = hashlib.sha256(remote.encode()).hexdigest()
    if _limited(rate_key, time.monotonic()):
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": "60"},
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": PUBLIC_ERRORS["RATE_LIMITED"],
                    "request_id": request_id_for(request),
                }
            },
        )
    cursor = db.scalar(
        select(IngestionCursor).where(IngestionCursor.webhook_key_hash == hook_hash)
    )
    if cursor is not None:
        now = utc_now()
        if cursor.next_poll_at > now:
            cursor.next_poll_at = now
            db.commit()
    return {"accepted": True}
