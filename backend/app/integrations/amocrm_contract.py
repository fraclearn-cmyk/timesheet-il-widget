"""Small, strict adapter for the amoCRM contracts validated in phase 0."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx


class AmoCRMTokenMissing(ValueError):
    """No server-side access token was supplied."""


class AmoCRMTokenExpired(ValueError):
    """amoCRM rejected an access token and it must be refreshed."""


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
            f"{account_url.rstrip('/')}/oauth2/access_token",
            content=urlencode(
                {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "authorization_code",
                    "code": authorization_code,
                    "redirect_uri": self._redirect_uri,
                }
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return _tokens_from_response(response)

    def get_account_context(
        self, account_url: str, *, access_token: str | None
    ) -> Mapping[str, Any]:
        if not access_token:
            raise AmoCRMTokenMissing("OAuth access token is required")

        response = self._http_client.get(
            f"{account_url.rstrip('/')}/api/v4/account",
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
            f"{account_url.rstrip('/')}/oauth2/access_token",
            content=urlencode(
                {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "redirect_uri": self._redirect_uri,
                }
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
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
    required = (
        "id",
        "type",
        "created_at",
        "created_by",
        "entity_id",
        "entity_type",
    )
    if not all(payload.get(field) is not None for field in required):
        return _incomplete_event(
            payload, source="crm_event", event_type="unknown_event"
        )

    links = payload.get("_links")
    self_link = links.get("self", {}) if isinstance(links, Mapping) else {}
    return {
        "external_id": str(payload["id"]),
        "kind": "confirmed",
        "source": "crm_event",
        "event_type": str(payload["type"]),
        "occurred_at": datetime.fromtimestamp(int(payload["created_at"]), UTC)
        .isoformat()
        .replace("+00:00", "Z"),
        "author_amocrm_id": int(payload["created_by"]),
        "object_type": str(payload["entity_type"]),
        "object_id": int(payload["entity_id"]),
        "object_url": self_link.get("href"),
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
