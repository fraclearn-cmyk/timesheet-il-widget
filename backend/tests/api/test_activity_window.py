"""Strict, account-scoped seven-local-date activity detail contract."""

from datetime import datetime, time
from uuid import UUID

from sqlalchemy import event

from app.models import (
    ActivityInterval,
    CallEvent,
    CrmEvent,
    GroupMember,
    User,
    WidgetGroup,
    WorkSession,
)
from app.models.user import UserRole
from app.models.work_session import WorkStatus


PATH = "/api/v1/team/2/activity?from=2026-03-27&to=2026-04-02"


def _error(response):
    return response.json()["error"]


def test_activity_detail_access_is_stricter_than_status_visibility(scoped_client, db):
    assert scoped_client("admin").get(PATH).status_code == 200
    assert scoped_client("manager").get(PATH).status_code == 200

    denied = [
        scoped_client("employee").get(PATH),
        scoped_client("employee").get(
            "/api/v1/team/3/activity?from=2026-03-27&to=2026-04-02"
        ),
        scoped_client("manager").get(
            "/api/v1/team/3/activity?from=2026-03-27&to=2026-04-02"
        ),
        scoped_client("admin").get(
            "/api/v1/team/4/activity?from=2026-03-27&to=2026-04-02"
        ),
        scoped_client("admin").get(
            "/api/v1/team/999/activity?from=2026-03-27&to=2026-04-02"
        ),
    ]
    assert {(item.status_code, _error(item)["code"]) for item in denied} == {
        (404, "NOT_FOUND")
    }
    assert len({_error(item)["message"] for item in denied}) == 1

    db.get(GroupMember, 1).is_active = False
    db.commit()
    assert scoped_client("manager").get(PATH).status_code == 404
    assert scoped_client("admin").get(PATH).status_code == 200

    db.get(GroupMember, 1).is_active = True
    db.get(User, 3).amocrm_role_id = 7000
    db.commit()
    assert scoped_client("manager").get(PATH).status_code == 404

    db.get(User, 2).is_active = False
    db.commit()
    response = scoped_client("admin").get(PATH)
    assert response.status_code == 404
    assert _error(response)["code"] == "NOT_FOUND"


def test_activity_range_validation_has_stable_public_errors(scoped_client):
    client = scoped_client("admin")
    for path in (
        "/api/v1/team/2/activity",
        "/api/v1/team/2/activity?from=nope&to=2026-04-02",
    ):
        response = client.get(path)
        assert response.status_code == 422
        assert _error(response)["code"] == "REQUEST_INVALID"

    reversed_range = client.get("/api/v1/team/2/activity?from=2026-04-02&to=2026-03-27")
    assert reversed_range.status_code == 400
    assert _error(reversed_range)["code"] == "ACTIVITY_RANGE_INVALID"

    too_large = client.get("/api/v1/team/2/activity?from=2026-03-26&to=2026-04-02")
    assert too_large.status_code == 400
    error = _error(too_large)
    assert error["code"] == "ACTIVITY_RANGE_TOO_LARGE"
    assert error["message"] == "Можно выбрать не больше 7 календарных дней."
    assert str(UUID(error["request_id"])) == error["request_id"]
    assert too_large.headers["X-Request-Id"] == error["request_id"]


def test_dst_overnight_window_clips_splits_and_resolves_safe_evidence(
    scoped_client, db
):
    group = db.get(WidgetGroup, 10)
    group.timezone = "Europe/Berlin"
    group.work_start_time = time(22)
    group.work_end_time = time(6)
    db.add_all(
        [
            WorkSession(
                id=500,
                amocrm_user_id=102,
                amocrm_account_id=10,
                user_name="Employee",
                start_time=datetime(2026, 3, 26, 20),
                end_time=datetime(2026, 4, 3),
                current_status=WorkStatus.FINISHED,
            ),
            ActivityInterval(
                id=101,
                account_id=10,
                user_id=2,
                work_session_id=500,
                started_at=datetime(2026, 3, 26, 22, 30),
                ended_at=datetime(2026, 3, 26, 23, 30),
                kind="confirmed",
                source="crm_event",
                duration_source="calculated",
                event_type="lead_status_changed",
                object_type="lead",
                object_id=1001,
                description="safe description",
            ),
            ActivityInterval(
                id=102,
                account_id=10,
                user_id=2,
                work_session_id=500,
                started_at=datetime(2026, 3, 28, 22, 30),
                ended_at=datetime(2026, 3, 28, 23, 30),
                kind="confirmed",
                source="crm_event",
                duration_source="calculated",
                event_type="lead_status_changed",
                object_type="lead",
                object_id=1002,
            ),
            ActivityInterval(
                id=103,
                account_id=10,
                user_id=2,
                work_session_id=500,
                started_at=datetime(2026, 3, 28, 23, 15),
                ended_at=datetime(2026, 3, 29, 0, 15),
                kind="confirmed",
                source="crm_event",
                duration_source="calculated",
                event_type="task_added",
                object_type="task",
                object_id=2002,
            ),
            ActivityInterval(
                id=104,
                account_id=10,
                user_id=2,
                work_session_id=500,
                started_at=datetime(2026, 3, 29, 8),
                ended_at=datetime(2026, 3, 29, 8),
                kind="confirmed",
                source="crm_event",
                duration_source="point",
                event_type="common_note_added",
                object_type="lead",
                object_id=1003,
            ),
            ActivityInterval(
                id=105,
                account_id=10,
                user_id=2,
                work_session_id=500,
                started_at=datetime(2026, 3, 29, 23),
                ended_at=datetime(2026, 3, 29, 23, 1),
                kind="confirmed",
                source="call",
                duration_source="observed",
                object_type="contact",
                object_id=3003,
            ),
            ActivityInterval(
                id=106,
                account_id=10,
                user_id=2,
                started_at=datetime(2026, 3, 29, 23, 30),
                ended_at=datetime(2026, 3, 30, 0),
                kind="unconfirmed",
                source="unconfirmed_input",
                duration_source="observed",
            ),
            ActivityInterval(
                id=107,
                account_id=10,
                user_id=2,
                work_session_id=500,
                started_at=datetime(2026, 3, 29, 12),
                ended_at=datetime(2026, 3, 29, 12),
                kind="confirmed",
                source="call",
                duration_source="observed",
                object_type="contact",
                object_id=3004,
            ),
            CrmEvent(
                account_id=10,
                external_id="crm-1002",
                author_amocrm_user_id=102,
                user_id=2,
                event_type="lead_status_changed",
                object_type="lead",
                object_id=1002,
                occurred_at=datetime(2026, 3, 28, 22, 45),
                card_url="https://tenant.amocrm.ru/api/v4/leads/1002",
                payload={"secret": "must-not-leak"},
                is_complete=1,
            ),
            CrmEvent(
                account_id=10,
                external_id="crm-wrong",
                author_amocrm_user_id=102,
                user_id=2,
                event_type="common_note_added",
                object_type="lead",
                object_id=9999,
                occurred_at=datetime(2026, 3, 29, 8),
                card_url="https://evil.invalid/card",
                payload={"raw": "hidden"},
                is_complete=1,
            ),
            CallEvent(
                account_id=10,
                source_event_id="call-3003",
                author_amocrm_user_id=102,
                user_id=2,
                direction="outgoing",
                occurred_at=datetime(2026, 3, 29, 23),
                duration_seconds=60,
                object_type="contact",
                object_id=3003,
                card_url="https://tenant.amocrm.ru/api/v4/contacts/3003",
                payload={"recording": "private"},
                is_complete=1,
            ),
            CallEvent(
                account_id=10,
                source_event_id="call-3004",
                author_amocrm_user_id=102,
                user_id=2,
                direction="incoming",
                occurred_at=datetime(2026, 3, 29, 12),
                duration_seconds=0,
                object_type="contact",
                object_id=3004,
                card_url="https://tenant.amocrm.ru/api/v4/contacts/3004",
                payload={"recording": "private-zero"},
                is_complete=1,
            ),
        ]
    )
    db.commit()

    response = scoped_client("admin").get(PATH)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["target"] == {
        "id": 2,
        "amocrm_user_id": 102,
        "name": "Employee",
        "avatar_url": None,
    }
    assert payload["group"]["id"] == 10
    assert payload["timezone"] == "Europe/Berlin"
    assert payload["from"] == "2026-03-27"
    assert payload["to"] == "2026-04-02"
    assert len(payload["days"]) == 7
    assert payload["days"][2]["started_at"] == "2026-03-28T23:00:00Z"
    assert payload["days"][2]["ended_at"] == "2026-03-29T22:00:00Z"
    assert payload["days"][1]["shift_started_at"] == "2026-03-28T21:00:00Z"
    assert payload["days"][1]["shift_ended_at"] == "2026-03-29T04:00:00Z"

    intervals = [item for day in payload["days"] for item in day["intervals"]]
    by_id = {}
    for item in intervals:
        by_id.setdefault(item["id"], []).append(item)
    assert by_id[101][0]["started_at"] == "2026-03-26T23:00:00Z"
    assert by_id[101][0]["duration_seconds"] == 1800
    assert [(x["started_at"], x["ended_at"]) for x in by_id[102]] == [
        ("2026-03-28T22:30:00Z", "2026-03-28T23:00:00Z"),
        ("2026-03-28T23:00:00Z", "2026-03-28T23:30:00Z"),
    ]
    assert by_id[104][0]["duration_seconds"] == 0
    assert by_id[104][0]["duration_source"] == "point"
    assert by_id[104][0]["card_url"] is None
    assert by_id[102][0]["card_url"].endswith("/api/v4/leads/1002")
    assert by_id[105][0]["call_direction"] == "outgoing"
    assert by_id[105][0]["call_duration_seconds"] == 60
    assert by_id[107][0]["call_direction"] == "incoming"
    assert by_id[107][0]["call_duration_seconds"] == 0
    assert by_id[107][0]["card_url"].endswith("/api/v4/contacts/3004")
    assert by_id[106][0]["kind"] == "unconfirmed"
    assert by_id[106][0]["message"] == "Нет подтверждённой активности"
    # Overlapping confirmed spans are merged: 30m clipped + 105m merged + 1m call.
    assert payload["totals"]["confirmed_seconds"] == 8_160
    assert payload["totals"]["confirmed_events"] == 6
    serialized = response.text.lower()
    assert "payload" not in serialized
    assert "secret" not in serialized
    assert "recording" not in serialized


def test_detail_query_count_and_duplicate_external_ids_stay_account_scoped(
    scoped_client, db
):
    for offset in range(40):
        account_id = 1000 + offset
        db.add(
            User(
                id=1000 + offset,
                amocrm_user_id=102,
                amocrm_account_id=account_id,
                name=f"Tenant {offset}",
                role=UserRole.EMPLOYEE,
                amocrm_rights={"is_admin": False, "role_id": 50},
                amocrm_role_id=50,
            )
        )
        db.add(WidgetGroup(id=1000 + offset, account_id=account_id, name=f"G {offset}"))
        db.add(
            ActivityInterval(
                account_id=account_id,
                user_id=1000 + offset,
                started_at=datetime(2026, 3, 29, 8),
                ended_at=datetime(2026, 3, 29, 9),
                kind="unconfirmed",
                source="unconfirmed_input",
                duration_source="observed",
            )
        )
    db.commit()

    selects = 0

    def count_selects(_conn, _cursor, statement, *_args):
        nonlocal selects
        if statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", count_selects)
    try:
        response = scoped_client("admin").get(PATH)
    finally:
        event.remove(engine, "before_cursor_execute", count_selects)

    assert response.status_code == 200
    assert response.json()["target"]["id"] == 2
    assert response.json()["days"][2]["intervals"] == []
    assert selects == 4


def test_evidence_queries_stay_inside_request_window_and_account(scoped_client, db):
    group = db.get(WidgetGroup, 10)
    group.timezone = "Europe/Berlin"
    utc_start = datetime(2026, 3, 26, 23)
    utc_end = datetime(2026, 4, 2, 22)
    years_start = datetime(2020, 1, 1)
    years_end = datetime(2030, 1, 1)
    measured_seconds = int((years_end - years_start).total_seconds())
    db.add(
        WorkSession(
            id=600,
            amocrm_user_id=102,
            amocrm_account_id=10,
            user_name="Employee",
            start_time=years_start,
            end_time=years_end,
            current_status=WorkStatus.FINISHED,
        )
    )
    db.add_all(
        [
            ActivityInterval(
                id=201,
                account_id=10,
                user_id=2,
                work_session_id=600,
                started_at=years_start,
                ended_at=years_end,
                kind="confirmed",
                source="crm_event",
                duration_source="calculated",
                event_type="lead_added",
                object_type="lead",
                object_id=9001,
            ),
            ActivityInterval(
                id=202,
                account_id=10,
                user_id=2,
                work_session_id=600,
                started_at=years_start,
                ended_at=years_end,
                kind="confirmed",
                source="call",
                duration_source="observed",
                object_type="contact",
                object_id=9002,
            ),
            CrmEvent(
                account_id=10,
                external_id="bounded-crm",
                author_amocrm_user_id=102,
                user_id=2,
                event_type="lead_added",
                object_type="lead",
                object_id=9001,
                occurred_at=utc_start,
                card_url="https://tenant.amocrm.ru/api/v4/leads/9001",
                is_complete=1,
            ),
            CrmEvent(
                account_id=10,
                external_id="right-edge-crm",
                author_amocrm_user_id=102,
                user_id=2,
                event_type="lead_added",
                object_type="lead",
                object_id=9001,
                occurred_at=utc_end,
                card_url="https://tenant.amocrm.ru/api/v4/leads/9001",
                is_complete=1,
            ),
            CallEvent(
                account_id=10,
                source_event_id="bounded-call",
                author_amocrm_user_id=102,
                user_id=2,
                direction="incoming",
                occurred_at=utc_start,
                duration_seconds=measured_seconds,
                object_type="contact",
                object_id=9002,
                card_url="https://tenant.amocrm.ru/api/v4/contacts/9002",
                is_complete=1,
            ),
            CallEvent(
                account_id=10,
                source_event_id="right-edge-call",
                author_amocrm_user_id=102,
                user_id=2,
                direction="outgoing",
                occurred_at=utc_end,
                duration_seconds=measured_seconds,
                object_type="contact",
                object_id=9002,
                card_url="https://tenant.amocrm.ru/api/v4/contacts/9002",
                is_complete=1,
            ),
        ]
    )
    for offset in range(40):
        account_id = 2000 + offset
        user_id = 2000 + offset
        db.add(
            User(
                id=user_id,
                amocrm_user_id=102,
                amocrm_account_id=account_id,
                name=f"Foreign {offset}",
                role=UserRole.EMPLOYEE,
            )
        )
        db.add_all(
            [
                ActivityInterval(
                    account_id=account_id,
                    user_id=user_id,
                    started_at=utc_start,
                    ended_at=utc_end,
                    kind="unconfirmed",
                    source="unconfirmed_input",
                    duration_source="observed",
                ),
                CrmEvent(
                    account_id=account_id,
                    external_id="bounded-crm",
                    author_amocrm_user_id=102,
                    user_id=user_id,
                    event_type="lead_added",
                    object_type="lead",
                    object_id=9001,
                    occurred_at=utc_start,
                    card_url="https://foreign.amocrm.ru/api/v4/leads/666",
                    is_complete=1,
                ),
                CallEvent(
                    account_id=account_id,
                    source_event_id="bounded-call",
                    author_amocrm_user_id=102,
                    user_id=user_id,
                    direction="outgoing",
                    occurred_at=utc_start,
                    duration_seconds=measured_seconds,
                    object_type="contact",
                    object_id=9002,
                    card_url="https://foreign.amocrm.ru/api/v4/contacts/666",
                    is_complete=1,
                ),
            ]
        )
    db.commit()

    response = scoped_client("admin").get(PATH)
    assert response.status_code == 200, response.text
    intervals = [item for day in response.json()["days"] for item in day["intervals"]]
    crm_segments = [item for item in intervals if item["id"] == 201]
    call_segments = [item for item in intervals if item["id"] == 202]
    assert len(crm_segments) == len(call_segments) == 7
    assert {item["card_url"] for item in crm_segments} == {
        "https://tenant.amocrm.ru/api/v4/leads/9001"
    }
    assert {item["call_direction"] for item in call_segments} == {"incoming"}
    assert {item["card_url"] for item in call_segments} == {
        "https://tenant.amocrm.ru/api/v4/contacts/9002"
    }
