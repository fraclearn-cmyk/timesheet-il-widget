"""Untrusted webhook trigger: it can only make an authoritative poll due."""

from __future__ import annotations

from collections import OrderedDict, deque
import hashlib
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.time_utils import utc_now
from app.api.v1.dependencies import APIProblem
from app.core.middleware import request_id_for
from app.models import IngestionCursor


router = APIRouter()
_MAX_BODY_BYTES = 64 * 1024
_RATE_LIMIT = 10
_RATE_WINDOW_SECONDS = 60.0
_MAX_RATE_BUCKETS = 4096
_requests: OrderedDict[str, deque[float]] = OrderedDict()


def _payload_too_large() -> APIProblem:
    return APIProblem(
        413,
        "PAYLOAD_TOO_LARGE",
        "Размер запроса превышает 64 КиБ.",
    )


def reset_webhook_rate_limits() -> None:
    _requests.clear()


def _limited(key: str, now: float) -> bool:
    attempts = _requests.get(key)
    if attempts is None:
        if len(_requests) >= _MAX_RATE_BUCKETS:
            _requests.popitem(last=False)
        attempts = deque()
        _requests[key] = attempts
    else:
        _requests.move_to_end(key)
    while attempts and now - attempts[0] >= _RATE_WINDOW_SECONDS:
        attempts.popleft()
    if len(attempts) >= _RATE_LIMIT:
        return True
    attempts.append(now)
    return False


async def _body_within_limit(request: Request, limit: int) -> bool:
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            return False
    return True


@router.post("/amocrm/{hook_id}", status_code=202)
async def amocrm_webhook(hook_id: str, request: Request, db: Session = Depends(get_db)):
    hook_hash = hashlib.sha256(hook_id.encode()).hexdigest()
    remote = request.client.host if request.client else "unknown"
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _MAX_BODY_BYTES:
                raise _payload_too_large()
        except ValueError:
            raise _payload_too_large()
    if not await _body_within_limit(request, _MAX_BODY_BYTES):
        raise _payload_too_large()
    # One bounded bucket per remote prevents random unknown IDs from growing memory.
    rate_key = hashlib.sha256(remote.encode()).hexdigest()
    if _limited(rate_key, time.monotonic()):
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": "60"},
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Слишком много запросов.",
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
