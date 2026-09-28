"""Fail-closed normalization for amoCRM activity evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Collection, Literal, Mapping, TypeGuard

from app.integrations.amocrm_contract import (
    AmoCRMAccountURLInvalid,
    _resource_origin,
    _trusted_tenant_origin,
    _validated_embedded_entity_url,
    _validated_timeline_event,
)


# Conservative runtime floor observed during phase-0 amoCRM verification. The
# account-scoped catalog remains authoritative and extends this recognition set.
OBSERVED_MINIMUM_EVENT_TYPES = frozenset(
    {
        "contact_added",
        "company_added",
        "lead_added",
        "entity_linked",
        "task_added",
        "common_note_added",
        "name_field_changed",
    }
)


@dataclass(frozen=True)
class NormalizedActivityEvent:
    external_id: str | None
    source: Literal["crm_event", "call"]
    normalized_type: str
    original_type: str | None
    occurred_at: datetime | None
    author_amocrm_user_id: int | None
    object_type: str | None
    object_id: int | None
    card_url: str | None
    direction: Literal["incoming", "outgoing"] | None
    duration_seconds: int | None
    is_complete: bool
    error_code: str | None


def canonical_payload_hash(
    *,
    account_id: int,
    source: str,
    external_id: str | None,
    occurred_at: datetime | None,
    payload: Mapping[str, Any],
) -> str:
    """Return an account-scoped, deterministic SHA-256 ingestion key."""
    canonical: dict[str, Any] = {
        "account_id": account_id,
        "source": source,
        "external_id": external_id,
        "occurred_at": _canonical_datetime(occurred_at),
    }
    if external_id is None:
        canonical["payload"] = payload
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_crm_event(
    payload: Mapping[str, Any],
    *,
    expected_account_id: int,
    expected_origin: str,
    known_types: Collection[str],
) -> NormalizedActivityEvent:
    """Normalize a CRM event only when every attribution check succeeds."""
    external_id = _external_id(payload.get("id"))
    original_type = payload.get("type")
    original_type = original_type if isinstance(original_type, str) else None
    base = _partial_event(
        payload,
        source="crm_event",
        normalized_type=original_type or "unknown",
        original_type=original_type,
    )

    if external_id is None:
        return _incomplete(base, "invalid_external_id", external_id=None)
    if not _account_matches(payload, expected_account_id):
        return _incomplete(base, "account_mismatch", external_id=external_id)
    if original_type is None or original_type not in known_types:
        return _incomplete(
            base,
            "unknown_event_type",
            external_id=external_id,
            normalized_type="unknown",
        )

    occurred_at = _utc_datetime(payload.get("created_at"))
    if occurred_at is None:
        return _incomplete(base, "invalid_timestamp", external_id=external_id)
    author_id = payload.get("created_by")
    if not _is_positive_int(author_id):
        return _incomplete(
            base,
            "invalid_author",
            external_id=external_id,
            occurred_at=occurred_at,
        )
    entity_id = payload.get("entity_id")
    entity_type = payload.get("entity_type")
    if not _is_positive_int(entity_id) or not _valid_entity_type(entity_type):
        return _incomplete(
            base,
            "invalid_entity",
            external_id=external_id,
            occurred_at=occurred_at,
            author_amocrm_user_id=author_id,
        )

    card_url = _crm_entity_url(payload, expected_origin)
    if card_url is None:
        return _incomplete(
            base,
            "invalid_entity_link",
            external_id=external_id,
            occurred_at=occurred_at,
            author_amocrm_user_id=author_id,
            object_type=entity_type,
            object_id=entity_id,
        )

    return NormalizedActivityEvent(
        external_id=external_id,
        source="crm_event",
        normalized_type=original_type,
        original_type=original_type,
        occurred_at=occurred_at,
        author_amocrm_user_id=author_id,
        object_type=entity_type,
        object_id=entity_id,
        card_url=card_url,
        direction=None,
        duration_seconds=None,
        is_complete=True,
        error_code=None,
    )


def normalize_call_event(
    payload: Mapping[str, Any],
    *,
    expected_account_id: int,
    expected_origin: str,
    source_verified: bool,
) -> NormalizedActivityEvent:
    """Normalize a call only after its source and every fact are verified."""
    external_id = _external_id(payload.get("id"))
    original_type = payload.get("type")
    original_type = original_type if isinstance(original_type, str) else None
    base = _partial_event(
        payload,
        source="call",
        normalized_type="unknown_call",
        original_type=original_type,
    )

    if source_verified is not True:
        return _incomplete(base, "unverified_call_source", external_id=external_id)
    if external_id is None:
        return _incomplete(base, "invalid_external_id", external_id=None)
    if not _account_matches(payload, expected_account_id):
        return _incomplete(base, "account_mismatch", external_id=external_id)

    occurred_at = _utc_datetime(payload.get("created_at"))
    if occurred_at is None:
        return _incomplete(base, "invalid_timestamp", external_id=external_id)
    author_id = payload.get("created_by")
    if not _is_positive_int(author_id):
        return _incomplete(
            base,
            "invalid_author",
            external_id=external_id,
            occurred_at=occurred_at,
        )
    entity_id = payload.get("entity_id")
    entity_type = payload.get("entity_type")
    if not _is_positive_int(entity_id) or not _valid_entity_type(entity_type):
        return _incomplete(
            base,
            "invalid_entity",
            external_id=external_id,
            occurred_at=occurred_at,
            author_amocrm_user_id=author_id,
        )

    direction = payload.get("direction")
    if direction not in ("incoming", "outgoing"):
        return _incomplete(
            base,
            "invalid_call_direction",
            external_id=external_id,
            occurred_at=occurred_at,
            author_amocrm_user_id=author_id,
            object_type=entity_type,
            object_id=entity_id,
        )
    duration = payload.get("duration_seconds")
    if not _is_nonnegative_int(duration):
        return _incomplete(
            base,
            "invalid_call_duration",
            external_id=external_id,
            occurred_at=occurred_at,
            author_amocrm_user_id=author_id,
            object_type=entity_type,
            object_id=entity_id,
        )

    card_url = _validated_embedded_entity_url(
        payload,
        expected_origin=expected_origin,
        parent_resource="calls",
    )
    if card_url is None:
        return _incomplete(
            base,
            "invalid_entity_link",
            external_id=external_id,
            occurred_at=occurred_at,
            author_amocrm_user_id=author_id,
            object_type=entity_type,
            object_id=entity_id,
        )

    return NormalizedActivityEvent(
        external_id=external_id,
        source="call",
        normalized_type="call",
        original_type=original_type,
        occurred_at=occurred_at,
        author_amocrm_user_id=author_id,
        object_type=entity_type,
        object_id=entity_id,
        card_url=card_url,
        direction=direction,
        duration_seconds=duration,
        is_complete=True,
        error_code=None,
    )


def _partial_event(
    payload: Mapping[str, Any],
    *,
    source: Literal["crm_event", "call"],
    normalized_type: str,
    original_type: str | None,
) -> NormalizedActivityEvent:
    entity_type = payload.get("entity_type")
    entity_id = payload.get("entity_id")
    author_id = payload.get("created_by")
    return NormalizedActivityEvent(
        external_id=_external_id(payload.get("id")),
        source=source,
        normalized_type=normalized_type,
        original_type=original_type,
        occurred_at=_utc_datetime(payload.get("created_at")),
        author_amocrm_user_id=author_id if _is_positive_int(author_id) else None,
        object_type=entity_type if _valid_entity_type(entity_type) else None,
        object_id=entity_id if _is_positive_int(entity_id) else None,
        card_url=None,
        direction=None,
        duration_seconds=None,
        is_complete=False,
        error_code=None,
    )


def _incomplete(
    event: NormalizedActivityEvent,
    error_code: str,
    **changes: Any,
) -> NormalizedActivityEvent:
    return replace(
        event,
        card_url=None,
        direction=None,
        duration_seconds=None,
        is_complete=False,
        error_code=error_code,
        **changes,
    )


def _crm_entity_url(payload: Mapping[str, Any], expected_origin: str) -> str | None:
    card_url = _validated_embedded_entity_url(
        payload,
        expected_origin=expected_origin,
        parent_resource="events",
    )
    if card_url is not None:
        return card_url

    legacy = _validated_timeline_event(payload)
    if legacy is None:
        return None
    object_url = legacy["object_url"]
    entity_type = legacy["entity_type"]
    entity_id = legacy["entity_id"]
    if str(entity_type).endswith("s"):
        expected_path = f"/{entity_type}/detail/{entity_id}"
    else:
        resources = {
            "contact": "contacts",
            "company": "companies",
            "lead": "leads",
            "task": "tasks",
        }
        resource = resources.get(str(entity_type))
        if resource is None:
            return None
        expected_path = f"/api/v4/{resource}/{entity_id}"
    origin = _resource_origin(object_url, expected_path)
    try:
        trusted_origin = _trusted_tenant_origin(expected_origin)
    except AmoCRMAccountURLInvalid:
        return None
    return object_url if origin == trusted_origin else None


def _account_matches(payload: Mapping[str, Any], expected_account_id: int) -> bool:
    if not _is_positive_int(expected_account_id):
        return False
    account_ids: list[object] = []
    if "account_id" in payload:
        account_ids.append(payload["account_id"])
    embedded = payload.get("_embedded")
    if isinstance(embedded, Mapping) and "account" in embedded:
        account = embedded["account"]
        account_ids.append(account.get("id") if isinstance(account, Mapping) else None)
    return bool(account_ids) and all(
        _is_positive_int(account_id) and account_id == expected_account_id
        for account_id in account_ids
    )


def _external_id(value: object) -> str | None:
    if _is_positive_int(value):
        return str(value)
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        return value
    return None


def _utc_datetime(value: object) -> datetime | None:
    if not _is_positive_int(value):
        return None
    try:
        return datetime.fromtimestamp(value, UTC).replace(tzinfo=None)
    except (OSError, OverflowError, ValueError):
        return None


def _canonical_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    else:
        value = value.astimezone(UTC)
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _is_positive_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_nonnegative_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_entity_type(value: object) -> bool:
    return isinstance(value, str) and value in {
        "contact",
        "company",
        "lead",
        "task",
        "contacts",
        "companies",
        "leads",
        "tasks",
    }
