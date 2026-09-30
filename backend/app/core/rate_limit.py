"""Bounded process-local ingress counters.

Authenticated requests are keyed only after server-side authentication has
produced a trusted account/user identity. Public and failed-authentication
traffic uses a separate bucket keyed from ``request.client``; forwarded browser
headers are intentionally ignored.

These counters protect one application worker. A multi-worker deployment must
also enforce a shared limit at its trusted reverse proxy/API gateway when a
cluster-wide quota is required.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from math import ceil
from threading import Lock
import time

from app.core.config import settings


class BoundedSlidingWindowLimiter:
    """A fixed-memory sliding-window limiter for one Python process."""

    def __init__(
        self,
        *,
        calls_per_period: int,
        period_seconds: int,
        max_buckets: int,
    ) -> None:
        self.calls_per_period = calls_per_period
        self.period_seconds = period_seconds
        self.max_buckets = max_buckets
        self.requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        with self._lock:
            attempts = self.requests.get(key)
            if attempts is None:
                if len(self.requests) >= self.max_buckets:
                    self.requests.popitem(last=False)
                attempts = deque()
                self.requests[key] = attempts
            else:
                self.requests.move_to_end(key)
            while attempts and current - attempts[0] >= self.period_seconds:
                attempts.popleft()
            if len(attempts) >= self.calls_per_period:
                retry_after = max(
                    1, ceil(self.period_seconds - (current - attempts[0]))
                )
                return True, retry_after
            attempts.append(current)
            return False, self.period_seconds

    def reset(self) -> None:
        with self._lock:
            self.requests.clear()


class BoundedConcurrencyGuard:
    """Cap simultaneous expensive work without charging completed requests."""

    def __init__(self, *, max_concurrent_per_key: int, max_buckets: int) -> None:
        self.max_concurrent_per_key = max_concurrent_per_key
        self.max_buckets = max_buckets
        self.active: OrderedDict[str, int] = OrderedDict()
        self._lock = Lock()

    def acquire(self, key: str) -> bool:
        with self._lock:
            current = self.active.get(key)
            if current is None:
                if len(self.active) >= self.max_buckets:
                    return False
                self.active[key] = 1
                return True
            self.active.move_to_end(key)
            if current >= self.max_concurrent_per_key:
                return False
            self.active[key] = current + 1
            return True

    def release(self, key: str) -> None:
        with self._lock:
            current = self.active.get(key)
            if current is None:
                return
            if current <= 1:
                del self.active[key]
            else:
                self.active[key] = current - 1

    def reset(self) -> None:
        with self._lock:
            self.active.clear()


_MAX_BUCKETS = getattr(settings, "RATE_LIMIT_MAX_BUCKETS", 4096)
authenticated_request_limiter = BoundedSlidingWindowLimiter(
    calls_per_period=settings.RATE_LIMIT_CALLS,
    period_seconds=settings.RATE_LIMIT_PERIOD,
    max_buckets=_MAX_BUCKETS,
)
unknown_request_limiter = BoundedSlidingWindowLimiter(
    calls_per_period=settings.RATE_LIMIT_CALLS,
    period_seconds=settings.RATE_LIMIT_PERIOD,
    max_buckets=_MAX_BUCKETS,
)
authentication_concurrency_guard = BoundedConcurrencyGuard(
    max_concurrent_per_key=settings.AUTHENTICATION_MAX_CONCURRENT_PER_IP,
    max_buckets=_MAX_BUCKETS,
)


def trusted_remote_key(request) -> str:
    """Use the socket peer only; client-supplied proxy headers are untrusted."""
    return request.client.host if request.client else "unknown"


def authenticated_identity_key(context) -> str:
    """Build a bucket from identity already verified by the server."""
    return f"account:{context.account_id}:user:{context.user.id}"
