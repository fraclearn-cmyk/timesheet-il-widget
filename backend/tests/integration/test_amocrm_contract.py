"""Mock contracts at the amoCRM boundary.

These tests use complete fixtures for the fields consumed by the adapter.  They
are intentionally isolated from a real amoCRM account: live verification is
recorded separately in the phase report.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.integrations.amocrm_contract import (
    AmoCRMAuthClient,
    AmoCRMTokenExpired,
    AmoCRMTokenMissing,
    normalize_call_event,
    normalize_timeline_event,
)


ACCOUNT_URL = "https://example.amocrm.ru"


@pytest.fixture
def observed_event() -> dict:
    """Synthetic projection of observed fields, never a copied live payload."""
    fixture = Path(__file__).parent / "fixtures" / "amocrm_observed_event.json"
    return json.loads(fixture.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("event_type", "entity_type", "object_url"),
    [
        ("contact_added", "contact", f"{ACCOUNT_URL}/api/v4/contacts/1001"),
        ("company_added", "company", f"{ACCOUNT_URL}/api/v4/companies/1001"),
        ("lead_added", "lead", f"{ACCOUNT_URL}/api/v4/leads/1001"),
        ("entity_linked", "contact", f"{ACCOUNT_URL}/api/v4/contacts/1001"),
        ("entity_linked", "company", f"{ACCOUNT_URL}/api/v4/companies/1001"),
        ("entity_linked", "lead", f"{ACCOUNT_URL}/api/v4/leads/1001"),
        ("task_added", "task", f"{ACCOUNT_URL}/api/v4/tasks/1001"),
        ("common_note_added", "lead", f"{ACCOUNT_URL}/api/v4/leads/1001"),
        ("name_field_changed", "lead", f"{ACCOUNT_URL}/api/v4/leads/1001"),
    ],
)
def test_normalizes_observed_event_with_opaque_id_and_embedded_entity_link(
    observed_event: dict, event_type: str, entity_type: str, object_url: str
) -> None:
    """Integer-only IDs or reading event self as entity self loses live activity."""
    observed_event["type"] = event_type
    observed_event["entity_type"] = entity_type
    observed_event["_embedded"]["entity"]["_links"]["self"]["href"] = object_url

    event = normalize_timeline_event(observed_event)

    assert event == {
        "external_id": "synthetic_event-A1",
        "kind": "confirmed",
        "source": "crm_event",
        "event_type": event_type,
        "occurred_at": "2026-09-11T08:00:00Z",
        "author_amocrm_id": 456,
        "object_type": entity_type,
        "object_id": 1001,
        "object_url": object_url,
        "raw_payload": observed_event,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", ""),
        ("id", " "),
        ("id", "x" * 129),
        ("id", "event/id"),
        ("id", "event%2Fid"),
        ("id", "event\nid"),
        ("id", "event\x00id"),
        ("id", "событие"),
        ("id", None),
        ("id", True),
        ("id", 9001),
        ("id", {}),
        ("type", "lead_deleted"),
        ("type", "lead_status_changed"),
        ("type", "contact_added"),
        ("type", "task_added"),
        ("type", []),
        ("created_at", "1789113600"),
        ("created_at", True),
        ("created_at", 0),
        ("created_at", 10**100),
        ("created_by", "456"),
        ("created_by", False),
        ("created_by", 0),
        ("created_by", -1),
        ("entity_id", True),
        ("entity_id", "1001"),
        ("entity_id", 0),
        ("entity_type", "leads"),
        ("entity_type", []),
        ("_embedded", None),
        ("_embedded", {"entity": []}),
        ("_embedded", {"entity": {"id": 1001, "_links": None}}),
        ("_links", {"self": []}),
    ],
)
def test_rejects_malformed_observed_event_without_raising(
    observed_event: dict, field: str, value: object
) -> None:
    """Unknown contexts and invalid attribution must stay incomplete."""
    observed_event[field] = value

    event = normalize_timeline_event(observed_event)

    assert event["kind"] == "incomplete_event"
    assert event["event_type"] == "unknown_event"
    assert event["object_url"] is None
    assert event["raw_payload"] == observed_event


@pytest.mark.parametrize("embedded_id", [None, True, "1001", 1002])
def test_rejects_observed_entity_id_mismatch(
    observed_event: dict, embedded_id: object
) -> None:
    observed_event["_embedded"]["entity"]["id"] = embedded_id
    assert normalize_timeline_event(observed_event)["kind"] == "incomplete_event"


@pytest.mark.parametrize("location", ["entity", "event"])
@pytest.mark.parametrize(
    "href",
    [
        None,
        42,
        "not a URL",
        "https://[broken",
        "http://example.amocrm.ru/api/v4/leads/1001",
        "https://attacker.invalid/api/v4/leads/1001",
        "https://other.amocrm.ru/api/v4/leads/1001",
        "https://example.amocrm.ru.attacker.invalid/api/v4/leads/1001",
        "https://user@example.amocrm.ru/api/v4/leads/1001",
        "https://example.amocrm.ru:443/api/v4/leads/1001",
        "https://bad host.amocrm.ru/api/v4/leads/1001",
        "https://example.amocrm.ru/api/v4/leads/1002",
        "https://example.amocrm.ru/api/v4/contacts/1001",
        "https://example.amocrm.ru/api/v4/leads/1001?redirect=external",
        "https://example.amocrm.ru/api/v4/leads/1001#fragment",
        "https://example.amocrm.ru/api/v4/leads/1001/",
        "https://example.amocrm.ru/api/v4/leads/%31%30%30%31",
        "\nhttps://example.amocrm.ru/api/v4/leads/1001",
        "https://example.amocrm.ru/api/v4/leads/10\n01",
        "https://example.amocrm.ru/leads/detail/1001",
        "https://example.amocrm.ru/api/v4/events/another-event",
    ],
)
def test_rejects_observed_external_or_malformed_links(
    observed_event: dict, location: str, href: object
) -> None:
    """Only matching entity/event paths on the same trusted tenant are usable."""
    target = observed_event
    if location == "entity":
        target = observed_event["_embedded"]["entity"]
    target["_links"]["self"]["href"] = href

    assert normalize_timeline_event(observed_event)["kind"] == "incomplete_event"


def test_exchanges_authorization_code_for_refreshable_token_set() -> None:
    """A wrong OAuth grant payload must not yield a usable token set."""

    def handler(request: httpx.Request) -> httpx.Response:
        if (
            request.method != "POST"
            or str(request.url) != f"{ACCOUNT_URL}/oauth2/access_token"
            or request.headers.get("Content-Type") != "application/json"
            or json.loads(request.content)
            != {
                "client_id": "client-id",
                "client_secret": "client-secret",
                "grant_type": "authorization_code",
                "code": "authorization-code",
                "redirect_uri": "https://widget.example/oauth/callback",
            }
        ):
            return httpx.Response(422, json={"title": "unexpected OAuth request"})
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )

    client = AmoCRMAuthClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://widget.example/oauth/callback",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    tokens = client.exchange_authorization_code(ACCOUNT_URL, "authorization-code")

    assert tokens.access_token == "access-token"
    assert tokens.refresh_token == "refresh-token"
    assert tokens.expires_in == 86400


def test_rejects_missing_access_token_before_calling_amocrm() -> None:
    """Token validation must precede use of SDK IDs as identity."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    client = AmoCRMAuthClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://widget.example/oauth/callback",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(AmoCRMTokenMissing):
        client.get_account_context(ACCOUNT_URL, access_token=None)

    assert calls == 0


def test_refreshes_expired_access_token_with_stored_refresh_token() -> None:
    """Refreshing through authorization_code would lose a renewed session."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Content-Type") != "application/json" or json.loads(
            request.content
        ) != {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "grant_type": "refresh_token",
            "refresh_token": "refresh-token",
            "redirect_uri": "https://widget.example/oauth/callback",
        }:
            return httpx.Response(422, json={"title": "unexpected refresh request"})
        return httpx.Response(
            200,
            json={
                "access_token": "renewed-access-token",
                "refresh_token": "rotated-refresh-token",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )

    client = AmoCRMAuthClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://widget.example/oauth/callback",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    tokens = client.refresh_access_token(ACCOUNT_URL, "refresh-token")

    assert tokens.access_token == "renewed-access-token"
    assert tokens.refresh_token == "rotated-refresh-token"


@pytest.mark.parametrize(
    "untrusted_url",
    [
        "http://tenant.amocrm.ru",
        "https://tenant.amocrm.ru.attacker.invalid",
        "https://attacker.invalid",
        "https://tenant.amocrm.ru:not-a-port",
        "https://tenant.kommo.com/oauth2/access_token",
    ],
)
def test_rejects_untrusted_tenant_url_before_sending_oauth_secret(
    untrusted_url: str,
) -> None:
    """An attacker URL must never receive the OAuth client secret."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "expires_in": 86400,
            },
        )

    client = AmoCRMAuthClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://widget.example/oauth/callback",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ValueError, match="trusted HTTPS amoCRM/Kommo tenant"):
        client.exchange_authorization_code(untrusted_url, "authorization-code")

    assert calls == 0


def test_marks_unauthorized_account_request_as_expired_token() -> None:
    """A changed 401 branch must not produce usable account context."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization") != "Bearer expired-access-token":
            return httpx.Response(422, json={"title": "missing bearer token"})
        return httpx.Response(
            401,
            json={
                "title": "Unauthorized",
                "type": "https://httpstatuses.com/401",
            },
        )

    client = AmoCRMAuthClient(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="https://widget.example/oauth/callback",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(AmoCRMTokenExpired):
        client.get_account_context(ACCOUNT_URL, access_token="expired-access-token")


def test_normalizes_complete_timeline_event_without_inventing_fields() -> None:
    """A missing amoCRM field must not silently create a confirmed interval."""
    event = normalize_timeline_event(
        {
            "id": 9001,
            "type": "lead_status_changed",
            "created_at": 1_789_113_600,
            "created_by": 456,
            "entity_id": 1001,
            "entity_type": "leads",
            "_links": {"self": {"href": "https://example.amocrm.ru/leads/detail/1001"}},
        }
    )

    assert event == {
        "external_id": "9001",
        "kind": "confirmed",
        "source": "crm_event",
        "event_type": "lead_status_changed",
        "occurred_at": "2026-09-11T08:00:00Z",
        "author_amocrm_id": 456,
        "object_type": "leads",
        "object_id": 1001,
        "object_url": "https://example.amocrm.ru/leads/detail/1001",
        "raw_payload": {
            "id": 9001,
            "type": "lead_status_changed",
            "created_at": 1_789_113_600,
            "created_by": 456,
            "entity_id": 1001,
            "entity_type": "leads",
            "_links": {"self": {"href": "https://example.amocrm.ru/leads/detail/1001"}},
        },
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "9001"),
        ("type", "lead_deleted"),
        ("type", 17),
        ("created_at", "not-a-unix-timestamp"),
        ("created_by", "456"),
        ("entity_id", True),
        ("entity_type", "contacts"),
        ("_links", {"self": {"href": 42}}),
        ("_links", {"self": {"href": "not a URL"}}),
        (
            "_links",
            {"self": {"href": "https://attacker.invalid/leads/detail/1001"}},
        ),
    ],
)
def test_marks_unknown_or_malformed_timeline_event_incomplete(
    field: str, value: object
) -> None:
    """Unknown types and invalid values must not make confirmed activity."""
    payload = {
        "id": 9001,
        "type": "lead_status_changed",
        "created_at": 1_789_113_600,
        "created_by": 456,
        "entity_id": 1001,
        "entity_type": "leads",
        "_links": {"self": {"href": "https://example.amocrm.ru/leads/detail/1001"}},
    }
    payload[field] = value

    event = normalize_timeline_event(payload)

    assert event["kind"] == "incomplete_event"
    assert event["source"] == "crm_event"
    assert event["event_type"] == "unknown_event"
    assert event["raw_payload"] == payload


def test_marks_unsupported_call_payload_incomplete() -> None:
    """An opaque call payload must not imply direction or duration."""
    payload = {"id": "call-17", "provider": "telephony", "opaque": True}

    event = normalize_call_event(payload)

    assert event == {
        "external_id": "call-17",
        "kind": "incomplete_event",
        "source": "call",
        "event_type": "unknown_call",
        "occurred_at": None,
        "author_amocrm_id": None,
        "object_type": None,
        "object_id": None,
        "object_url": None,
        "direction": None,
        "duration_seconds": None,
        "raw_payload": payload,
    }
