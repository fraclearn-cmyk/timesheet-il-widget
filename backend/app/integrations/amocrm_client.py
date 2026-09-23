"""Conservative asynchronous transport for the verified amoCRM API surface."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlsplit

import httpx

from app.integrations.amocrm_contract import (
    AmoCRMAccountURLInvalid,
    _trusted_tenant_origin,
)


class AmoCRMClientError(RuntimeError):
    """Base class for safe amoCRM transport failures."""


class AmoCRMRateLimited(AmoCRMClientError):
    """amoCRM kept returning 429 after the bounded retry budget."""


class AmoCRMUnavailable(AmoCRMClientError):
    """A timeout or transient upstream response exhausted the retry budget."""


@dataclass(frozen=True)
class AmoCRMEventPage:
    items: Sequence[Mapping[str, Any]]
    next_url: str | None


class AmoCRMClient:
    """Make bounded, credential-redacting JSON requests to amoCRM."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.25,
        max_pages: int = 100,
        max_items: int = 10_000,
    ) -> None:
        if max_retries < 0 or max_pages < 1 or max_items < 1:
            raise ValueError("retry, page and item limits must be positive")
        self._http = http_client
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._max_pages = max_pages
        self._max_items = max_items

    async def get_json(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> Mapping[str, Any]:
        """Return JSON, retrying only transient failures a bounded number of times."""
        payload = await self._get_json(url, headers=headers)
        if payload is None:
            raise AmoCRMClientError("amoCRM returned an unexpected empty response")
        return payload

    async def _get_json(
        self, url: str, *, headers: Mapping[str, str] | None = None
    ) -> Mapping[str, Any] | None:
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.get(
                    url, headers=headers, timeout=self._timeout
                )
            except (httpx.TimeoutException, httpx.TransportError) as error:
                if attempt == self._max_retries:
                    raise AmoCRMUnavailable(
                        "amoCRM is temporarily unavailable"
                    ) from error
                await self._sleep(attempt)
                continue
            if response.status_code == 429:
                if attempt == self._max_retries:
                    raise AmoCRMRateLimited("amoCRM rate limit exceeded")
                await asyncio.sleep(self._retry_after(response, attempt))
                continue
            if response.status_code in {502, 503, 504}:
                if attempt == self._max_retries:
                    raise AmoCRMUnavailable("amoCRM is temporarily unavailable")
                await self._sleep(attempt)
                continue
            response.raise_for_status()
            if response.status_code == 204:
                return None
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise AmoCRMClientError("amoCRM returned an unexpected JSON payload")
            return payload
        raise AssertionError("retry loop must return or raise")

    async def list_events_page(
        self,
        account_url: str,
        access_token: str,
        *,
        created_from: int,
        page_url: str | None = None,
    ) -> AmoCRMEventPage:
        """Read one bounded events page and accept only same-tenant next links."""
        origin = self._trusted_origin(account_url)
        if page_url is None:
            url = str(
                httpx.URL(
                    f"{origin}/api/v4/events",
                    params={
                        "limit": "100",
                        "filter[created_at][from]": str(created_from),
                    },
                )
            )
        else:
            url = self._validated_event_page_url(origin, page_url, requested=True)

        payload = await self._get_json(
            url, headers={"Authorization": f"Bearer {access_token}"}
        )
        if payload is None:
            return AmoCRMEventPage(items=(), next_url=None)
        embedded = payload.get("_embedded")
        items = embedded.get("events") if isinstance(embedded, Mapping) else None
        if not isinstance(items, list) or not all(
            isinstance(item, Mapping) for item in items
        ):
            raise AmoCRMClientError("amoCRM returned an unexpected events payload")
        if len(items) > self._max_items:
            raise AmoCRMClientError("amoCRM event pagination exceeded item budget")

        links = payload.get("_links")
        next_link = links.get("next") if isinstance(links, Mapping) else None
        next_value = next_link.get("href") if isinstance(next_link, Mapping) else None
        next_url = None
        if next_value is not None:
            if not isinstance(next_value, str):
                raise AmoCRMClientError("amoCRM returned an untrusted next link")
            next_url = self._validated_event_page_url(origin, next_value)
        return AmoCRMEventPage(items=tuple(items), next_url=next_url)

    async def list_event_types(
        self, account_url: str, access_token: str
    ) -> Sequence[tuple[str, str | None]]:
        """Return the account-scoped amoCRM event catalog as key/label pairs."""
        origin = self._trusted_origin(account_url)
        payload = await self._get_json(
            f"{origin}/api/v4/events/types",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if payload is None:
            return ()
        embedded = payload.get("_embedded")
        entries = (
            embedded.get("events_types") if isinstance(embedded, Mapping) else None
        )
        if not isinstance(entries, list):
            raise AmoCRMClientError("amoCRM returned an unexpected event type catalog")
        result: list[tuple[str, str | None]] = []
        for entry in entries:
            if not isinstance(entry, Mapping) or not isinstance(entry.get("key"), str):
                raise AmoCRMClientError(
                    "amoCRM returned an unexpected event type catalog"
                )
            label = entry.get("lang")
            if label is not None and not isinstance(label, str):
                raise AmoCRMClientError(
                    "amoCRM returned an unexpected event type catalog"
                )
            result.append((entry["key"], label))
        if len(result) > self._max_items:
            raise AmoCRMClientError("amoCRM event type catalog exceeded item budget")
        return tuple(result)

    async def get_account(
        self, account_url: str, access_token: str
    ) -> Mapping[str, Any]:
        return await self.get_json(
            f"{account_url}/api/v4/account",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    async def list_users(
        self, account_url: str, access_token: str
    ) -> list[Mapping[str, Any]]:
        """Read only explicit next links; never invent page traversal semantics."""
        url = f"{account_url}/api/v4/users?limit=250&page=1"
        users: list[Mapping[str, Any]] = []
        seen_urls: set[str] = set()
        while url not in seen_urls:
            if len(seen_urls) >= self._max_pages:
                raise AmoCRMClientError("amoCRM user pagination exceeded page budget")
            seen_urls.add(url)
            payload = await self.get_json(
                url, headers={"Authorization": f"Bearer {access_token}"}
            )
            embedded = payload.get("_embedded")
            page_users = (
                embedded.get("users") if isinstance(embedded, Mapping) else None
            )
            if not isinstance(page_users, list):
                break
            users.extend(item for item in page_users if isinstance(item, Mapping))
            if len(users) > self._max_items:
                raise AmoCRMClientError("amoCRM user pagination exceeded item budget")
            links = payload.get("_links")
            next_link = links.get("next") if isinstance(links, Mapping) else None
            next_url = next_link.get("href") if isinstance(next_link, Mapping) else None
            if not isinstance(next_url, str) or not next_url.startswith(
                account_url + "/"
            ):
                break
            url = next_url
        return users

    async def _sleep(self, attempt: int) -> None:
        await asyncio.sleep(self._backoff * (2**attempt))

    def _retry_after(self, response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, min(float(value), 60.0))
            except ValueError:
                try:
                    delta = parsedate_to_datetime(value).astimezone(
                        timezone.utc
                    ) - datetime.now(timezone.utc)
                    return max(0.0, min(delta.total_seconds(), 60.0))
                except (TypeError, ValueError):
                    pass
        return self._backoff * (2**attempt)

    @staticmethod
    def _trusted_origin(account_url: str) -> str:
        try:
            return _trusted_tenant_origin(account_url)
        except AmoCRMAccountURLInvalid as error:
            raise AmoCRMClientError("amoCRM account URL is not trusted") from error

    def _validated_event_page_url(
        self, origin: str, candidate: str, *, requested: bool = False
    ) -> str:
        message = (
            "amoCRM event page URL is not trusted"
            if requested
            else ("amoCRM returned an untrusted next link")
        )
        try:
            parsed = urlsplit(candidate)
            port = parsed.port
        except ValueError as error:
            raise AmoCRMClientError(message) from error
        expected = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or parsed.hostname != expected.hostname
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or parsed.path != "/api/v4/events"
            or parsed.fragment
        ):
            raise AmoCRMClientError(message)
        pages = parse_qs(parsed.query).get("page", [])
        if pages:
            try:
                page_number = int(pages[-1])
            except ValueError as error:
                raise AmoCRMClientError(message) from error
            if page_number < 1:
                raise AmoCRMClientError(message)
        return candidate
