"""One PostgreSQL gate for the complete local phase-5 activity pipeline."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.dependencies import get_request_context
from app.core.access_policy import RequestContext
from app.core.database import get_db
from app.integrations.amocrm_client import AmoCRMEventPage
from app.models import (
    ActivityInterval,
    CallEvent,
    CrmEvent,
    GroupMember,
    IngestionCursor,
    OAuthConnection,
    RawIngestionEvent,
    StatusTransition,
    User,
    WidgetGroup,
    WorkSession,
    WorkStatus,
)
from app.services.activity_interval_service import ActivityIntervalService
from app.services.event_ingestion_service import EventIngestionService
from app.services.event_normalizer import normalize_call_event
from test_migrations import migrated_db as _postgres_fixture


migrated_db = _postgres_fixture

ACCOUNT_ID = 501
AMOCRM_USER_ID = 7001
ACCOUNT_URL = "https://phase5.amocrm.ru"
STARTED_AT = datetime(2026, 9, 23, 9)
BREAK_AT = STARTED_AT + timedelta(minutes=10)
RESUMED_AT = STARTED_AT + timedelta(minutes=20)
EVENT_AT = STARTED_AT + timedelta(minutes=5)


def test_empty_public_base_url_keeps_polling_only_deployment_valid() -> None:
    from app.core.config import Settings, settings

    values = settings.model_dump()
    values["PUBLIC_BASE_URL"] = ""

    assert Settings(**values).PUBLIC_BASE_URL is None


class _OAuth:
    def load_access_token(self, _connection: OAuthConnection) -> str:
        return "server-side-token"


class _ReplayClient:
    def __init__(self, items):
        self.items = tuple(items)

    async def list_event_types(self, _account_url: str, _access_token: str):
        return [("lead_added", "Lead added")]

    async def list_events_page(
        self,
        _account_url: str,
        _access_token: str,
        *,
        created_from: int,
        page_url: str | None = None,
    ) -> AmoCRMEventPage:
        assert created_from >= 0
        assert page_url is None
        return AmoCRMEventPage(items=self.items, next_url=None)


def _crm_event(event_id: str, *, event_type: str = "lead_added", author=AMOCRM_USER_ID):
    timestamp = int(EVENT_AT.replace(tzinfo=UTC).timestamp())
    return {
        "id": event_id,
        "type": event_type,
        "created_at": timestamp,
        "created_by": author,
        "account_id": ACCOUNT_ID,
        "entity_id": 9001,
        "entity_type": "lead",
        "_links": {"self": {"href": f"{ACCOUNT_URL}/api/v4/events/{event_id}"}},
        "_embedded": {
            "account": {"id": ACCOUNT_ID},
            "entity": {
                "id": 9001,
                "_links": {"self": {"href": f"{ACCOUNT_URL}/api/v4/leads/9001"}},
            },
        },
    }


def _presence(window_started_at: datetime, last_seen_at: datetime):
    def iso(value: datetime) -> str:
        return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")

    return {
        "command_id": str(uuid4()),
        "window_started_at": iso(window_started_at),
        "last_seen_at": iso(last_seen_at),
        "signal_count": 5,
    }


def test_phase5_pipeline_is_deduplicated_bounded_and_fail_closed(
    migrated_db, monkeypatch
) -> None:
    config, engine = migrated_db
    command.upgrade(config, "head")

    with Session(engine) as db:
        user = User(
            id=71,
            amocrm_account_id=ACCOUNT_ID,
            amocrm_user_id=AMOCRM_USER_ID,
            name="Phase 5 employee",
        )
        group = WidgetGroup(
            id=81,
            account_id=ACCOUNT_ID,
            name="Phase 5 group",
            timezone="UTC",
        )
        work = WorkSession(
            id=91,
            amocrm_account_id=ACCOUNT_ID,
            amocrm_user_id=AMOCRM_USER_ID,
            user_name=user.name,
            start_time=STARTED_AT,
            current_status=WorkStatus.WORKING,
        )
        db.add_all(
            [
                user,
                group,
                OAuthConnection(
                    account_id=ACCOUNT_ID,
                    account_url=ACCOUNT_URL,
                    encrypted_access_token="encrypted-access",
                    encrypted_refresh_token="encrypted-refresh",
                    is_active=True,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                GroupMember(
                    account_id=ACCOUNT_ID,
                    group_id=group.id,
                    user_id=user.id,
                    track_time=True,
                    is_active=True,
                ),
                work,
            ]
        )
        db.flush()
        db.add_all(
            [
                StatusTransition(
                    work_session_id=work.id,
                    from_status=None,
                    to_status=WorkStatus.WORKING.value,
                    timestamp=STARTED_AT,
                ),
                StatusTransition(
                    work_session_id=work.id,
                    from_status=WorkStatus.WORKING.value,
                    to_status=WorkStatus.BREAK.value,
                    timestamp=BREAK_AT,
                ),
                StatusTransition(
                    work_session_id=work.id,
                    from_status=WorkStatus.BREAK.value,
                    to_status=WorkStatus.WORKING.value,
                    timestamp=RESUMED_AT,
                ),
            ]
        )
        db.commit()

        items = [
            _crm_event("same-time-a"),
            _crm_event("same-time-b"),
            _crm_event("system-event", author=0),
            _crm_event("unknown-event", event_type="future_type"),
        ]
        ingestion = EventIngestionService(
            db,
            _ReplayClient(items),
            _OAuth(),
            owner="phase5-pipeline",
            poll_interval_seconds=60,
        )
        assert asyncio.run(
            ingestion.ingest_account(
                account_id=ACCOUNT_ID, now=STARTED_AT + timedelta(minutes=9)
            )
        )
        assert asyncio.run(
            ingestion.ingest_account(
                account_id=ACCOUNT_ID,
                now=STARTED_AT + timedelta(minutes=9, seconds=30),
            )
        )

        unverified = normalize_call_event(
            {
                "id": "call-unverified",
                "type": "call",
                "created_at": int(
                    (BREAK_AT + timedelta(minutes=1)).replace(tzinfo=UTC).timestamp()
                ),
                "created_by": AMOCRM_USER_ID,
                "account_id": ACCOUNT_ID,
                "entity_id": 9001,
                "entity_type": "lead",
                "direction": "outgoing",
                "duration_seconds": 120,
            },
            expected_account_id=ACCOUNT_ID,
            expected_origin=ACCOUNT_URL,
            source_verified=False,
        )
        call = CallEvent(
            account_id=ACCOUNT_ID,
            source_event_id=unverified.external_id,
            author_amocrm_user_id=unverified.author_amocrm_user_id,
            user_id=None,
            direction=unverified.direction,
            occurred_at=unverified.occurred_at,
            duration_seconds=unverified.duration_seconds,
            object_type=unverified.object_type,
            object_id=unverified.object_id,
            card_url=unverified.card_url,
            payload=None,
            is_complete=0,
        )
        db.add(call)
        db.flush()
        assert ActivityIntervalService(db).attach_call(call) is None
        db.commit()

    from app.api.v1 import activity, webhooks
    from app.main import app

    def session_dependency():
        with Session(engine) as request_db:
            yield request_db

    with Session(engine) as db:
        context_user = db.get(User, 71)
        db.expunge(context_user)

    app.dependency_overrides[get_db] = session_dependency
    app.dependency_overrides[get_request_context] = lambda: RequestContext(
        ACCOUNT_ID, context_user
    )
    monkeypatch.setattr(
        activity,
        "utc_now",
        lambda: STARTED_AT + timedelta(minutes=8),
    )
    webhooks.reset_webhook_rate_limits()
    try:
        with TestClient(app) as client:
            first = client.post(
                "/api/v1/activity/presence",
                json=_presence(
                    STARTED_AT + timedelta(minutes=1),
                    STARTED_AT + timedelta(minutes=2),
                ),
            )
            second = client.post(
                "/api/v1/activity/presence",
                json=_presence(
                    STARTED_AT + timedelta(minutes=7, seconds=1),
                    STARTED_AT + timedelta(minutes=8),
                ),
            )
            assert first.status_code == second.status_code == 202

            with Session(engine) as db:
                before = (
                    db.scalar(select(func.count()).select_from(RawIngestionEvent)),
                    db.scalar(select(func.count()).select_from(CrmEvent)),
                    db.scalar(select(func.count()).select_from(ActivityInterval)),
                )
                cursor_before = db.get(IngestionCursor, ACCOUNT_ID).next_poll_at

            forged = client.post(
                "/api/v1/webhooks/amocrm/forged-hook-id",
                json={"id": "forged", "created_by": AMOCRM_USER_ID},
            )
            assert forged.status_code == 202

            with Session(engine) as db:
                after = (
                    db.scalar(select(func.count()).select_from(RawIngestionEvent)),
                    db.scalar(select(func.count()).select_from(CrmEvent)),
                    db.scalar(select(func.count()).select_from(ActivityInterval)),
                )
                cursor_after = db.get(IngestionCursor, ACCOUNT_ID).next_poll_at
    finally:
        app.dependency_overrides.clear()
        webhooks.reset_webhook_rate_limits()

    with Session(engine) as db:
        confirmed_points = db.scalar(
            select(func.count())
            .select_from(ActivityInterval)
            .where(
                ActivityInterval.kind == "confirmed",
                ActivityInterval.source == "crm_event",
                ActivityInterval.duration_source == "point",
                ActivityInterval.started_at == ActivityInterval.ended_at,
            )
        )
        measured_call_intervals = db.scalar(
            select(func.count())
            .select_from(ActivityInterval)
            .where(ActivityInterval.source == "call")
        )
        unconfirmed_intervals = db.scalar(
            select(func.count())
            .select_from(ActivityInterval)
            .where(ActivityInterval.kind == "unconfirmed")
        )
        activity_during_break = db.scalar(
            select(func.count())
            .select_from(ActivityInterval)
            .where(
                ActivityInterval.started_at >= BREAK_AT,
                ActivityInterval.started_at < RESUMED_AT,
            )
        )
        duplicate_raw_rows = db.scalar(
            select(func.count()).select_from(
                select(
                    RawIngestionEvent.account_id,
                    RawIngestionEvent.source,
                    RawIngestionEvent.dedup_key,
                )
                .group_by(
                    RawIngestionEvent.account_id,
                    RawIngestionEvent.source,
                    RawIngestionEvent.dedup_key,
                )
                .having(func.count() > 1)
                .subquery()
            )
        )
        duplicate_crm_rows = db.scalar(
            select(func.count()).select_from(
                select(CrmEvent.account_id, CrmEvent.external_id)
                .group_by(CrmEvent.account_id, CrmEvent.external_id)
                .having(func.count() > 1)
                .subquery()
            )
        )

    forged_webhook_rows = sum(after) - sum(before)
    duplicate_rows = duplicate_raw_rows + duplicate_crm_rows

    assert confirmed_points == 2
    assert measured_call_intervals == 0
    assert unconfirmed_intervals == 2
    assert activity_during_break == 0
    assert duplicate_rows == 0
    assert forged_webhook_rows == 0
    assert cursor_after == cursor_before
