"""Small, strict adapter for the amoCRM contracts validated in phase 0."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx


class AmoCRMTokenMissing(ValueError):
    """No server-side access token was supplied."""


class AmoCRMTokenExpired(ValueError):
    """amoCRM rejected an access token and it must be refreshed."""


class AmoCRMAccountURLInvalid(ValueError):
    """The tenant origin is not a trusted amoCRM or Kommo HTTPS URL."""


@dataclass(frozen=True)
class AmoCRMTokens:
    access_token: str
    refresh_token: str
    expires_in: int


class AmoCRMAuthClient:
    """Authenticate only with OAuth credentials supplied by the server."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        http_client: httpx.Client,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._http_client = http_client

    def exchange_authorization_code(
        self, account_url: str, authorization_code: str
    ) -> AmoCRMTokens:
        if not authorization_code:
            raise AmoCRMTokenMissing("OAuth authorization code is required")

        response = self._http_client.post(
            f"{_trusted_tenant_origin(account_url)}/oauth2/access_token",
            json={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": self._redirect_uri,
            },
        )
        return _tokens_from_response(response)

    def get_account_context(
        self, account_url: str, *, access_token: str | None
    ) -> Mapping[str, Any]:
        if not access_token:
            raise AmoCRMTokenMissing("OAuth access token is required")

        response = self._http_client.get(
            f"{_trusted_tenant_origin(account_url)}/api/v4/account",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 401:
            raise AmoCRMTokenExpired("amoCRM access token was rejected")
        response.raise_for_status()
        return response.json()

    def refresh_access_token(
        self, account_url: str, refresh_token: str
    ) -> AmoCRMTokens:
        if not refresh_token:
            raise AmoCRMTokenMissing("OAuth refresh token is required")

        response = self._http_client.post(
            f"{_trusted_tenant_origin(account_url)}/oauth2/access_token",
            json={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "redirect_uri": self._redirect_uri,
            },
        )
        return _tokens_from_response(response)


def _tokens_from_response(response: httpx.Response) -> AmoCRMTokens:
    if response.status_code == 401:
        raise AmoCRMTokenExpired("amoCRM rejected OAuth credentials")
    response.raise_for_status()
    payload = response.json()
    required = ("access_token", "refresh_token", "expires_in")
    if not all(payload.get(field) for field in required):
        raise AmoCRMTokenExpired("amoCRM OAuth response lacks a required token field")
    return AmoCRMTokens(
        access_token=str(payload["access_token"]),
        refresh_token=str(payload["refresh_token"]),
        expires_in=int(payload["expires_in"]),
    )


def normalize_timeline_event(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return confirmed activity only for a fully attributed amoCRM event."""
    normalized = _validated_timeline_event(payload)
    if normalized is None:
        return _incomplete_event(
            payload, source="crm_event", event_type="unknown_event"
        )

    return {
        "external_id": str(normalized["id"]),
        "kind": "confirmed",
        "source": "crm_event",
        "event_type": normalized["type"],
        "occurred_at": datetime.fromtimestamp(normalized["created_at"], UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "author_amocrm_id": normalized["created_by"],
        "object_type": normalized["entity_type"],
        "object_id": normalized["entity_id"],
        "object_url": normalized["object_url"],
        "raw_payload": dict(payload),
    }


def normalize_call_event(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Keep an unverified call payload without inferring call attributes."""
    return {
        **_incomplete_event(payload, source="call", event_type="unknown_call"),
        "direction": None,
        "duration_seconds": None,
    }


def _incomplete_event(
    payload: Mapping[str, Any], *, source: str, event_type: str
) -> dict[str, Any]:
    return {
        "external_id": (str(payload["id"]) if payload.get("id") is not None else None),
        "kind": "incomplete_event",
        "source": source,
        "event_type": event_type,
        "occurred_at": None,
        "author_amocrm_id": None,
        "object_type": None,
        "object_id": None,
        "object_url": None,
        "raw_payload": dict(payload),
    }


def _trusted_tenant_origin(account_url: str) -> str:
    """Validate a server-side amoCRM/Kommo tenant origin before using secrets."""
    try:
        parsed = urlsplit(account_url)
        port = parsed.port
    except ValueError as error:
        raise AmoCRMAccountURLInvalid(
            "trusted HTTPS amoCRM/Kommo tenant is required"
        ) from error
    host = parsed.hostname.lower() if parsed.hostname else ""
    allowed_suffixes = (".amocrm.ru", ".amocrm.com", ".kommo.com")
    is_single_tenant = any(
        host.endswith(suffix)
        and host[: -len(suffix)]
        and "." not in host[: -len(suffix)]
        for suffix in allowed_suffixes
    )
    if (
        parsed.scheme != "https"
        or not is_single_tenant
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise AmoCRMAccountURLInvalid("trusted HTTPS amoCRM/Kommo tenant is required")
    return f"https://{host}"


def _validated_timeline_event(
    payload: Mapping[str, Any],
) -> dict[str, int | str] | None:
    """Accept only the mock-validated event shape; keep all else incomplete."""
    event_id = payload.get("id")
    event_type = payload.get("type")
    created_at = payload.get("created_at")
    created_by = payload.get("created_by")
    entity_id = payload.get("entity_id")
    entity_type = payload.get("entity_type")
    links = payload.get("_links")
    self_link = links.get("self") if isinstance(links, Mapping) else None
    object_url = self_link.get("href") if isinstance(self_link, Mapping) else None

    if (
        not all(
            _is_positive_int(value)
            for value in (event_id, created_at, created_by, entity_id)
        )
        or event_type != "lead_status_changed"
        or entity_type != "leads"
        or not isinstance(object_url, str)
        or not object_url
    ):
        return None

    try:
        datetime.fromtimestamp(created_at, UTC)
    except (OSError, OverflowError, ValueError):
        return None

    return {
        "id": event_id,
        "type": event_type,
        "created_at": created_at,
        "created_by": created_by,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "object_url": object_url,
    }


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
