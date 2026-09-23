from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import pytest

from app.services.event_normalizer import (
    NormalizedActivityEvent,
    canonical_payload_hash,
    normalize_call_event,
    normalize_crm_event,
)


ACCOUNT_ID = 108
ACCOUNT_ORIGIN = "https://example.amocrm.ru"
OCCURRED_AT = datetime(2026, 9, 23, 9, 0)
OCCURRED_AT_TIMESTAMP = 1_790_154_000

OFFICIAL_CATALOG_CASES = (
    ("contact_added", "contact", "contacts"),
    ("company_added", "company", "companies"),
    ("lead_added", "lead", "leads"),
    ("entity_linked", "lead", "leads"),
    ("task_added", "task", "tasks"),
    ("common_note_added", "lead", "leads"),
    ("name_field_changed", "lead", "leads"),
)


def crm_payload(
    *,
    event_type: str = "lead_added",
    entity_type: str = "lead",
    resource: str = "leads",
) -> dict:
    return {
        "id": "event-17",
        "account_id": ACCOUNT_ID,
        "type": event_type,
        "created_at": OCCURRED_AT_TIMESTAMP,
        "created_by": 456,
        "entity_id": 1001,
        "entity_type": entity_type,
        "_links": {"self": {"href": f"{ACCOUNT_ORIGIN}/api/v4/events/event-17"}},
        "_embedded": {
            "entity": {
                "id": 1001,
                "_links": {
                    "self": {"href": f"{ACCOUNT_ORIGIN}/api/v4/{resource}/1001"}
                },
            }
        },
    }


def call_payload() -> dict:
    return {
        "id": "call-17",
        "account_id": ACCOUNT_ID,
        "type": "call",
        "created_at": OCCURRED_AT_TIMESTAMP,
        "created_by": 456,
        "entity_id": 1001,
        "entity_type": "lead",
        "direction": "incoming",
        "duration_seconds": 91,
        "_links": {"self": {"href": f"{ACCOUNT_ORIGIN}/api/v4/calls/call-17"}},
        "_embedded": {
            "entity": {
                "id": 1001,
                "_links": {"self": {"href": f"{ACCOUNT_ORIGIN}/api/v4/leads/1001"}},
            }
        },
    }


@pytest.mark.parametrize(
    ("event_type", "entity_type", "resource"), OFFICIAL_CATALOG_CASES
)
def test_normalizes_each_known_catalog_event(
    event_type: str, entity_type: str, resource: str
) -> None:
    """Dropping a catalog key must not silently discard valid CRM evidence."""
    payload = crm_payload(
        event_type=event_type, entity_type=entity_type, resource=resource
    )

    result = normalize_crm_event(
        payload,
        expected_account_id=ACCOUNT_ID,
        expected_origin=ACCOUNT_ORIGIN,
        known_types={case[0] for case in OFFICIAL_CATALOG_CASES},
    )

    assert result == NormalizedActivityEvent(
        external_id="event-17",
        source="crm_event",
        normalized_type=event_type,
        original_type=event_type,
        occurred_at=OCCURRED_AT,
        author_amocrm_user_id=456,
        object_type=entity_type,
        object_id=1001,
        card_url=f"{ACCOUNT_ORIGIN}/api/v4/{resource}/1001",
        direction=None,
        duration_seconds=None,
        is_complete=True,
        error_code=None,
    )


def test_unknown_type_is_preserved_but_incomplete() -> None:
    """Treating an unrecognized type as confirmed would invent evidence."""
    payload = crm_payload(event_type="lead_deleted")

    result = normalize_crm_event(
        payload,
        expected_account_id=ACCOUNT_ID,
        expected_origin=ACCOUNT_ORIGIN,
        known_types={"lead_added"},
    )

    assert result.normalized_type == "unknown"
    assert result.original_type == "lead_deleted"
    assert result.is_complete is False
    assert result.error_code == "unknown_event_type"


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (lambda payload: payload.__setitem__("id", None), "invalid_external_id"),
        (lambda payload: payload.__setitem__("account_id", True), "account_mismatch"),
        (lambda payload: payload.__setitem__("account_id", 109), "account_mismatch"),
        (
            lambda payload: payload["_embedded"].__setitem__("account", {"id": 109}),
            "account_mismatch",
        ),
        (lambda payload: payload.__setitem__("created_by", True), "invalid_author"),
        (lambda payload: payload.__setitem__("created_by", 0), "invalid_author"),
        (lambda payload: payload.__setitem__("created_at", True), "invalid_timestamp"),
        (
            lambda payload: payload.__setitem__("created_at", 10**100),
            "invalid_timestamp",
        ),
        (lambda payload: payload.__setitem__("entity_id", True), "invalid_entity"),
        (
            lambda payload: payload["_embedded"]["entity"].__setitem__("id", 1002),
            "invalid_entity_link",
        ),
        (
            lambda payload: payload["_embedded"]["entity"]["_links"][
                "self"
            ].__setitem__("href", "https://attacker.invalid/api/v4/leads/1001"),
            "invalid_entity_link",
        ),
    ],
    ids=[
        "missing-id",
        "boolean-account",
        "foreign-account",
        "foreign-embedded-account",
        "boolean-author",
        "system-author",
        "boolean-timestamp",
        "invalid-timestamp",
        "boolean-entity",
        "mismatched-embedded-entity",
        "unsafe-link",
    ],
)
def test_malformed_crm_evidence_fails_closed(mutate, error_code: str) -> None:
    """Invalid attribution must never become a complete activity event."""
    payload = crm_payload()
    mutate(payload)

    result = normalize_crm_event(
        payload,
        expected_account_id=ACCOUNT_ID,
        expected_origin=ACCOUNT_ORIGIN,
        known_types={"lead_added"},
    )

    assert result.is_complete is False
    assert result.error_code == error_code
    assert result.direction is None
    assert result.duration_seconds is None


def test_normalized_event_is_immutable() -> None:
    """Mutating normalized evidence after validation would bypass fail-closed checks."""
    result = normalize_crm_event(
        crm_payload(),
        expected_account_id=ACCOUNT_ID,
        expected_origin=ACCOUNT_ORIGIN,
        known_types={"lead_added"},
    )

    with pytest.raises(AttributeError):
        result.is_complete = False  # type: ignore[misc]


def test_canonical_hash_is_stable_across_json_key_order() -> None:
    """Equivalent payload order must not create duplicate raw envelopes."""
    payload = {"nested": {"b": 2, "a": 1}, "items": [3, 2, 1]}
    reordered = {"items": [3, 2, 1], "nested": {"a": 1, "b": 2}}

    first = canonical_payload_hash(
        account_id=ACCOUNT_ID,
        source="crm_event",
        external_id=None,
        occurred_at=OCCURRED_AT,
        payload=payload,
    )
    second = canonical_payload_hash(
        account_id=ACCOUNT_ID,
        source="crm_event",
        external_id=None,
        occurred_at=OCCURRED_AT,
        payload=reordered,
    )

    assert first == second
    assert len(first) == 64


def test_canonical_hash_is_scoped_by_account_and_source() -> None:
    """Cross-account or cross-source evidence must never deduplicate together."""
    arguments = {
        "external_id": "event-17",
        "occurred_at": OCCURRED_AT,
        "payload": {"ignored_when_id_is_present": True},
    }

    crm_hash = canonical_payload_hash(
        account_id=ACCOUNT_ID, source="crm_event", **arguments
    )
    foreign_hash = canonical_payload_hash(
        account_id=109, source="crm_event", **arguments
    )
    call_hash = canonical_payload_hash(
        account_id=ACCOUNT_ID, source="call", **arguments
    )

    assert len({crm_hash, foreign_hash, call_hash}) == 3


def test_verified_complete_call_preserves_only_observed_call_facts() -> None:
    """A verified call with every required fact should retain actual duration."""
    result = normalize_call_event(
        call_payload(),
        expected_account_id=ACCOUNT_ID,
        expected_origin=ACCOUNT_ORIGIN,
        source_verified=True,
    )

    assert result == NormalizedActivityEvent(
        external_id="call-17",
        source="call",
        normalized_type="call",
        original_type="call",
        occurred_at=OCCURRED_AT,
        author_amocrm_user_id=456,
        object_type="lead",
        object_id=1001,
        card_url=f"{ACCOUNT_ORIGIN}/api/v4/leads/1001",
        direction="incoming",
        duration_seconds=91,
        is_complete=True,
        error_code=None,
    )


@pytest.mark.parametrize(
    ("source_verified", "field", "value"),
    [
        (False, None, None),
        (True, "id", ""),
        (True, "account_id", 109),
        (True, "created_by", 0),
        (True, "direction", "inbound"),
        (True, "duration_seconds", True),
        (True, "duration_seconds", -1),
        (True, "created_at", "2026-09-23T09:00:00Z"),
        (True, "entity_id", 0),
    ],
)
def test_unverified_or_incomplete_call_does_not_expose_guessed_facts(
    source_verified: bool, field: str | None, value: object
) -> None:
    """Any missing call fact must erase direction and duration from usable evidence."""
    payload = deepcopy(call_payload())
    if field is not None:
        payload[field] = value

    result = normalize_call_event(
        payload,
        expected_account_id=ACCOUNT_ID,
        expected_origin=ACCOUNT_ORIGIN,
        source_verified=source_verified,
    )

    assert result.source == "call"
    assert result.normalized_type == "unknown_call"
    assert result.is_complete is False
    assert result.direction is None
    assert result.duration_seconds is None
    assert result.error_code is not None
