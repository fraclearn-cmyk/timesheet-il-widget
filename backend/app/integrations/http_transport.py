"""amoCRM HTTP transports with an optional local interface binding."""

from __future__ import annotations

import httpx


def build_amocrm_sync_transport(
    local_address: str | None,
) -> httpx.HTTPTransport | None:
    if not local_address:
        return None
    return httpx.HTTPTransport(local_address=local_address)


def build_amocrm_async_transport(
    local_address: str | None,
    *,
    limits: httpx.Limits | None = None,
) -> httpx.AsyncHTTPTransport | None:
    if not local_address:
        return None
    if limits is None:
        return httpx.AsyncHTTPTransport(local_address=local_address)
    return httpx.AsyncHTTPTransport(local_address=local_address, limits=limits)
