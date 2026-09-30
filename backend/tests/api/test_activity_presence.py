from datetime import UTC, datetime, timedelta
from uuid import uuid4
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.dependencies import get_request_context
from app.core.access_policy import RequestContext
from app.core.database import Base, get_db
from app.models import ActivityInterval, PresenceBatch, User, WorkSession, WorkStatus


NOW = datetime(2026, 9, 23, 9, 1, tzinfo=UTC)


@pytest.fixture
def presence_api(monkeypatch):
    from app.main import app

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(id=1, amocrm_user_id=101, amocrm_account_id=10, name="Employee")
    foreign = User(id=2, amocrm_user_id=201, amocrm_account_id=11, name="Foreign")
    db.add_all(
        [
            user,
            foreign,
            WorkSession(
                id=1,
                amocrm_user_id=101,
                amocrm_account_id=10,
                user_name="Employee",
                start_time=datetime(2026, 9, 23, 9),
                current_status=WorkStatus.WORKING,
            ),
            WorkSession(
                id=2,
                amocrm_user_id=201,
                amocrm_account_id=11,
                user_name="Foreign",
                start_time=datetime(2026, 9, 23, 9),
                current_status=WorkStatus.WORKING,
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr("app.api.v1.activity.utc_now", lambda: NOW.replace(tzinfo=None))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_request_context] = lambda: RequestContext(10, user)
    with TestClient(app) as client:
        yield client, db, app, user, foreign
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def payload(command_id=None):
    return {
        "command_id": str(command_id or uuid4()),
        "window_started_at": "2026-09-23T09:00:00Z",
        "last_seen_at": "2026-09-23T09:00:44Z",
        "signal_count": 12,
    }


def test_presence_returns_canonical_interval_and_replay_is_idempotent(presence_api):
    client, db, _, _, _ = presence_api
    body = payload()

    first = client.post("/api/v1/activity/presence", json=body)
    second = client.post("/api/v1/activity/presence", json=body)

    assert first.status_code == second.status_code == 202
    assert (
        first.json()
        == second.json()
        == {
            "started_at": "2026-09-23T09:00:00Z",
            "ended_at": "2026-09-23T09:00:44Z",
            "kind": "unconfirmed",
            "source": "unconfirmed_input",
            "duration_source": "observed",
        }
    )
    assert db.query(PresenceBatch).count() == 1
    assert db.query(ActivityInterval).count() == 1


def test_presence_returns_no_content_outside_working(presence_api):
    client, db, _, _, _ = presence_api
    db.get(WorkSession, 1).current_status = WorkStatus.BREAK
    db.commit()

    response = client.post("/api/v1/activity/presence", json=payload())

    assert response.status_code == 204
    assert response.content == b""
    assert db.query(PresenceBatch).count() == 1
    assert db.query(ActivityInterval).count() == 0


@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"account_id": 10},
        {"user_id": 101},
        {"command_id": "not-a-uuid"},
        {"command_id": "00000000-0000-0000-0000-000000000000"},
        {"window_started_at": "2026-09-23T09:00:00"},
        {"last_seen_at": "not-a-time"},
        {"signal_count": 0},
        {"signal_count": 100001},
        {"signal_count": True},
    ],
)
def test_presence_rejects_extra_identity_and_invalid_fields(presence_api, change):
    client, db, _, _, _ = presence_api
    request_id = "de23640a-d8de-4fea-8ac8-184b593f34e5"
    body = payload()
    body.update(change)
    response = client.post(
        "/api/v1/activity/presence",
        json=body,
        headers={"X-Request-Id": request_id},
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "REQUEST_INVALID",
            "message": "Проверьте формат и значения полей запроса.",
            "request_id": request_id,
        }
    }
    assert response.headers["X-Request-Id"] == request_id
    assert db.query(PresenceBatch).count() == 0


@pytest.mark.parametrize(
    "start,end",
    [
        (NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)),
        (NOW - timedelta(minutes=11), NOW - timedelta(minutes=10, seconds=1)),
        (NOW - timedelta(seconds=10), NOW - timedelta(seconds=11)),
    ],
)
def test_presence_rejects_timestamps_outside_bounds(presence_api, start, end):
    client, db, _, _, _ = presence_api
    body = payload()
    body["window_started_at"] = start.isoformat()
    body["last_seen_at"] = end.isoformat()
    response = client.post("/api/v1/activity/presence", json=body)
    assert response.status_code == 422
    assert db.query(PresenceBatch).count() == 0


def test_presence_uses_only_the_verified_foreign_context(presence_api):
    client, db, app, _, foreign = presence_api
    app.dependency_overrides[get_request_context] = lambda: RequestContext(11, foreign)

    response = client.post("/api/v1/activity/presence", json=payload())

    assert response.status_code == 202
    batch = db.query(PresenceBatch).one()
    assert (batch.account_id, batch.user_id) == (11, 2)


def test_presence_rejects_a_forged_foreign_context(presence_api):
    client, db, app, _, foreign = presence_api
    app.dependency_overrides[get_request_context] = lambda: SimpleNamespace(
        account_id=10, user=foreign, privileges_verified=True
    )

    response = client.post("/api/v1/activity/presence", json=payload())

    assert response.status_code == 422
    assert db.query(PresenceBatch).count() == 0
