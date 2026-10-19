from datetime import datetime, timedelta, time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.access_policy import RequestContext
from app.core.database import Base
from app.models import (
    GroupMember,
    LatenessIncident,
    StatusTransition,
    TimesheetCommand,
    User,
    WidgetGroup,
    WorkSession,
)
from app.services.timesheet_service import TimesheetConflict, TimesheetService


NOW = datetime(2026, 9, 22, 6)


@pytest.mark.parametrize(
    "start,end,now,day,late",
    [
        (time(9), time(18), datetime(2026, 9, 22, 6), "2026-09-22", 0),
        (time(9), time(18), datetime(2026, 9, 22, 6, 17), "2026-09-22", 17),
        (time(22), time(6), datetime(2026, 9, 22, 19), "2026-09-22", 0),
        (time(22), time(6), datetime(2026, 9, 22, 22, 15), "2026-09-22", 195),
    ],
)
def test_start_work_persists_group_shift_lateness(scope, start, end, now, day, late):
    db, context, group = scope
    group.work_start_time, group.work_end_time = start, end
    db.commit()
    TimesheetService(db).apply(context, "start-work", uuid4(), now_utc=now)
    work = db.query(WorkSession).one()
    assert work.business_date.isoformat() == day
    assert work.start_time == now and work.start_time.tzinfo is None
    assert work.late_minutes == late
    assert work.is_late is (late > 0)


@pytest.fixture
def scope():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, amocrm_account_id=10, amocrm_user_id=101, name="One")
        group = WidgetGroup(id=1, account_id=10, name="Sales", timezone="Europe/Minsk")
        db.add_all([user, group])
        db.flush()
        db.add(
            GroupMember(
                account_id=10, user_id=1, group_id=1, is_active=True, track_time=True
            )
        )
        db.commit()
        yield db, RequestContext(10, user), group
    engine.dispose()


def test_full_cycle_persists_history_and_utc_naive_times(scope):
    db, context, _ = scope
    service = TimesheetService(db)
    assert service.get_status(context, NOW).status == "not_started"
    snapshots = [
        service.apply(context, action, uuid4(), now_utc=NOW + timedelta(minutes=i))
        for i, action in enumerate(
            ("start-work", "start-break", "end-break", "finish-work")
        )
    ]
    assert [s.status for s in snapshots] == [
        "working",
        "on_break",
        "working",
        "finished",
    ]
    assert db.query(StatusTransition).count() == 4
    work = db.query(WorkSession).one()
    assert work.business_date.isoformat() == "2026-09-22"
    assert work.start_time == NOW
    assert work.end_time == NOW + timedelta(minutes=3)
    assert snapshots[-1].break_seconds == 60


def test_same_key_replays_original_response_without_transition(scope):
    db, context, _ = scope
    service = TimesheetService(db)
    key = UUID("11111111-1111-4111-8111-111111111111")
    first = service.apply(context, "start-work", key, now_utc=NOW)
    assert (
        service.apply(context, "start-work", key, now_utc=NOW + timedelta(seconds=5))
        == first
    )
    assert db.query(StatusTransition).count() == 1
    with pytest.raises(TimesheetConflict, match="IDEMPOTENCY_KEY_REUSED"):
        service.apply(context, "start-break", key, now_utc=NOW)


def test_invalid_transition_and_restart_permission(scope):
    db, context, group = scope
    service = TimesheetService(db)
    with pytest.raises(TimesheetConflict, match="STATUS_TRANSITION_INVALID"):
        service.apply(context, "start-break", uuid4(), now_utc=NOW)
    service.apply(context, "start-work", uuid4(), now_utc=NOW)
    service.apply(context, "finish-work", uuid4(), now_utc=NOW + timedelta(minutes=1))
    with pytest.raises(TimesheetConflict, match="STATUS_TRANSITION_INVALID"):
        service.apply(
            context, "start-work", uuid4(), now_utc=NOW + timedelta(minutes=2)
        )
    group.allow_restart_session = True
    assert (
        service.apply(
            context, "start-work", uuid4(), now_utc=NOW + timedelta(minutes=2)
        ).status
        == "working"
    )
    assert db.query(WorkSession).count() == 2


def test_restart_permission_allows_only_one_additional_session_per_day(scope):
    db, context, group = scope
    service = TimesheetService(db)
    member = db.query(GroupMember).one()
    member.require_late_reason = True
    group.allow_restart_session = True
    db.commit()

    service.apply(context, "start-work", uuid4(), now_utc=NOW)
    service.apply(context, "finish-work", uuid4(), now_utc=NOW + timedelta(minutes=1))
    service.apply(
        context,
        "start-work",
        uuid4(),
        reason="повторный запуск разрешён",
        now_utc=NOW + timedelta(minutes=2),
    )
    second_finish = service.apply(
        context, "finish-work", uuid4(), now_utc=NOW + timedelta(minutes=3)
    )

    assert second_finish.restart_allowed is False
    assert second_finish.late_reason_required is False
    with pytest.raises(TimesheetConflict, match="STATUS_TRANSITION_INVALID"):
        service.apply(
            context,
            "start-work",
            uuid4(),
            reason="третий запуск запрещён",
            now_utc=NOW + timedelta(minutes=4),
        )
    assert db.query(WorkSession).count() == 2


def test_track_time_false_denies_commands(scope):
    db, context, _ = scope
    db.query(GroupMember).one().track_time = False
    db.commit()
    with pytest.raises(TimesheetConflict, match="TRACK_TIME_DISABLED"):
        TimesheetService(db).apply(context, "start-work", uuid4(), now_utc=NOW)


def test_open_prior_business_day_remains_authoritative(scope):
    db, context, _ = scope
    service = TimesheetService(db)
    first = service.apply(context, "start-work", uuid4(), now_utc=NOW)
    next_day = NOW + timedelta(days=1)
    assert service.get_status(context, next_day).session_id == first.session_id
    assert service.get_status(context, next_day).status == "working"
    with pytest.raises(TimesheetConflict, match="STATUS_TRANSITION_INVALID"):
        service.apply(context, "start-work", uuid4(), now_utc=next_day)
    assert (
        service.apply(context, "finish-work", uuid4(), now_utc=next_day).status
        == "finished"
    )


def test_account_identity_keeps_same_external_user_and_key_independent(scope):
    db, context, _ = scope
    other = User(id=2, amocrm_account_id=11, amocrm_user_id=101, name="Other")
    group = WidgetGroup(id=2, account_id=11, name="Other", timezone="UTC")
    db.add_all([other, group])
    db.flush()
    db.add(
        GroupMember(
            account_id=11, user_id=2, group_id=2, is_active=True, track_time=True
        )
    )
    db.commit()
    key = uuid4()
    first = TimesheetService(db).apply(context, "start-work", key, now_utc=NOW)
    second = TimesheetService(db).apply(
        RequestContext(11, other), "start-work", key, now_utc=NOW
    )
    assert second.session_id != first.session_id
    assert db.query(StatusTransition).count() == 2


@pytest.mark.parametrize("seconds,minutes", [(-1, 0), (0, 0), (1, 1), (60, 1), (61, 2)])
def test_shift_rounding_records_incident_even_without_required_reason(
    scope, seconds, minutes
):
    db, context, _ = scope
    TimesheetService(db).apply(
        context, "start-work", uuid4(), now_utc=NOW + timedelta(seconds=seconds)
    )
    work = db.query(WorkSession).one()
    assert work.late_minutes == minutes
    incidents = db.query(LatenessIncident).all()
    assert len(incidents) == int(minutes > 0)
    if incidents:
        incident = incidents[0]
        assert (
            incident.account_id,
            incident.amocrm_user_id,
            incident.work_session_id,
        ) == (10, 101, work.id)
        assert (
            incident.kind.value,
            incident.sequence,
            incident.late_minutes,
            incident.reason,
        ) == ("shift_start", 0, minutes, None)


@pytest.mark.parametrize("reason", [None, "", " \t\n "])
@pytest.mark.parametrize("action", ["start-work", "end-break"])
def test_required_reason_rejects_before_any_command_mutation(scope, reason, action):
    db, context, _ = scope
    member = db.query(GroupMember).one()
    member.require_late_reason = True
    db.commit()
    service = TimesheetService(db)
    if action == "end-break":
        service.apply(context, "start-work", uuid4(), now_utc=NOW)
        service.apply(context, "start-break", uuid4(), now_utc=NOW)
    at = NOW + timedelta(hours=1, seconds=1)
    before = (
        db.query(WorkSession).count(),
        db.query(StatusTransition).count(),
        db.query(TimesheetCommand).count(),
    )
    with pytest.raises(TimesheetConflict, match="LATE_REASON_REQUIRED") as caught:
        service.apply(context, action, uuid4(), reason=reason, now_utc=at)
    assert caught.value.details == {
        "kind": "shift_start" if action == "start-work" else "break_return",
        "late_minutes": 61 if action == "start-work" else 1,
        "sequence": 0 if action == "start-work" else 1,
    }
    assert (
        db.query(WorkSession).count(),
        db.query(StatusTransition).count(),
        db.query(TimesheetCommand).count(),
    ) == before
    assert db.query(LatenessIncident).count() == 0
    status = service.get_status(context, at)
    assert status.late_reason_required is True
    assert status.late_minutes == (61 if action == "start-work" else 1)
    assert status.break_sequence == (None if action == "start-work" else 1)


@pytest.mark.parametrize("action", ["start-work", "end-break"])
def test_reason_is_trimmed_accepts_1000_characters_and_rejects_1001(scope, action):
    db, context, _ = scope
    db.query(GroupMember).one().require_late_reason = True
    db.commit()
    service = TimesheetService(db)
    if action == "end-break":
        service.apply(context, "start-work", uuid4(), now_utc=NOW)
        service.apply(context, "start-break", uuid4(), now_utc=NOW)
    at = NOW + timedelta(hours=2)
    with pytest.raises(TimesheetConflict, match="INVALID_REASON"):
        service.apply(context, action, uuid4(), reason="x" * 1001, now_utc=at)
    result = service.apply(
        context, action, uuid4(), reason="  " + "x" * 1000 + " \n", now_utc=at
    )
    assert result.status == "working" and result.late_reason_required is False
    incident = db.query(LatenessIncident).one()
    assert incident.reason == "x" * 1000
    if action == "start-work":
        assert db.query(WorkSession).one().late_reason == incident.reason


@pytest.mark.parametrize(
    "seconds,minutes", [(3599, 0), (3600, 0), (3601, 1), (3661, 2)]
)
def test_break_boundary_and_rounding(scope, seconds, minutes):
    db, context, _ = scope
    service = TimesheetService(db)
    service.apply(context, "start-work", uuid4(), now_utc=NOW)
    service.apply(context, "start-break", uuid4(), now_utc=NOW)
    service.apply(
        context, "end-break", uuid4(), now_utc=NOW + timedelta(seconds=seconds)
    )
    incidents = db.query(LatenessIncident).all()
    assert len(incidents) == int(minutes > 0)
    if incidents:
        assert (
            incidents[0].kind.value,
            incidents[0].sequence,
            incidents[0].late_minutes,
            incidents[0].reason,
        ) == ("break_return", 1, minutes, None)


def test_current_break_limit_multiple_sequences_restart_and_finish_on_break(scope):
    db, context, group = scope
    service = TimesheetService(db)
    db.query(GroupMember).one().require_late_reason = True
    group.allow_restart_session = True
    db.commit()
    service.apply(context, "start-work", uuid4(), now_utc=NOW)
    service.apply(context, "start-break", uuid4(), now_utc=NOW)
    group.break_limit_minutes = 10
    db.commit()
    assert service.get_status(context, NOW + timedelta(minutes=11)).late_minutes == 1
    service.apply(
        context, "end-break", uuid4(), reason="one", now_utc=NOW + timedelta(minutes=11)
    )
    service.apply(context, "start-break", uuid4(), now_utc=NOW + timedelta(minutes=12))
    service.apply(
        context, "end-break", uuid4(), reason="two", now_utc=NOW + timedelta(minutes=24)
    )
    service.apply(context, "start-break", uuid4(), now_utc=NOW + timedelta(minutes=25))
    service.apply(context, "finish-work", uuid4(), now_utc=NOW + timedelta(minutes=40))
    assert (
        service.get_status(context, NOW + timedelta(minutes=40)).late_reason_required
        is True
    )
    service.apply(
        context,
        "start-work",
        uuid4(),
        reason="restart",
        now_utc=NOW + timedelta(minutes=40),
    )
    incidents = db.query(LatenessIncident).order_by(LatenessIncident.id).all()
    assert [(i.kind.value, i.sequence, i.late_minutes) for i in incidents] == [
        ("break_return", 1, 1),
        ("break_return", 2, 2),
        ("shift_start", 0, 40),
    ]
    assert len({i.work_session_id for i in incidents}) == 2
    assert (
        db.query(WorkSession).order_by(WorkSession.id).first().total_break_time == 2280
    )


def test_normalized_reason_hash_replays_once_and_changed_payload_conflicts(scope):
    db, context, _ = scope
    service = TimesheetService(db)
    key = uuid4()
    first = service.apply(
        context,
        "start-work",
        key,
        reason="  bus \n",
        now_utc=NOW + timedelta(seconds=1),
    )
    assert (
        service.apply(
            context, "start-work", key, reason="bus", now_utc=NOW + timedelta(hours=1)
        )
        == first
    )
    for action, reason in [("start-work", "train"), ("start-break", "bus")]:
        with pytest.raises(TimesheetConflict, match="IDEMPOTENCY_KEY_REUSED"):
            service.apply(context, action, key, reason=reason, now_utc=NOW)
    command = db.query(TimesheetCommand).one()
    assert len(command.request_hash) == 64 and "bus" not in command.request_hash
    assert db.query(LatenessIncident).count() == db.query(StatusTransition).count() == 1


def test_late_incident_rolls_back_with_failed_command(scope, monkeypatch):
    db, context, _ = scope
    service = TimesheetService(db)
    real_commit = db.commit

    def fail_commit():
        db.flush()
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        service.apply(
            context,
            "start-work",
            uuid4(),
            reason="bus",
            now_utc=NOW + timedelta(minutes=1),
        )
    monkeypatch.setattr(db, "commit", real_commit)
    assert (
        db.query(WorkSession).count()
        == db.query(LatenessIncident).count()
        == db.query(StatusTransition).count()
        == db.query(TimesheetCommand).count()
        == 0
    )


def test_50_accounts_with_shared_external_identity_and_key_are_independent(scope):
    db, context, _ = scope
    key = uuid4()
    contexts = [context]
    for i in range(2, 51):
        user = User(id=i, amocrm_account_id=i + 9, amocrm_user_id=101, name=f"User {i}")
        group = WidgetGroup(
            id=i, account_id=i + 9, name=f"Group {i}", timezone="Europe/Minsk"
        )
        db.add_all([user, group])
        db.flush()
        db.add(GroupMember(account_id=i + 9, user_id=i, group_id=i, track_time=True))
        contexts.append(RequestContext(i + 9, user))
    db.commit()
    for index, caller in enumerate(contexts):
        TimesheetService(db).apply(
            caller,
            "start-work",
            key,
            reason=f"reason {index}",
            now_utc=NOW + timedelta(seconds=1),
        )
    incidents = db.query(LatenessIncident).all()
    assert len(incidents) == len({i.account_id for i in incidents}) == 50
    assert len({i.work_session_id for i in incidents}) == 50
    for index, caller in enumerate(contexts):
        incident = next(i for i in incidents if i.account_id == caller.account_id)
        assert incident.reason == f"reason {index}"
    from types import SimpleNamespace

    with pytest.raises(TimesheetConflict, match="ACCOUNT_SCOPE_INVALID"):
        TimesheetService(db).apply(
            SimpleNamespace(account_id=11, user=context.user),
            "start-work",
            key,
            reason="reason 1",
            now_utc=NOW,
        )


@pytest.mark.parametrize("action", ["start-work", "end-break"])
def test_requirement_does_not_block_equal_boundary_or_aware_utc_clock(scope, action):
    from datetime import timezone

    db, context, _ = scope
    db.query(GroupMember).one().require_late_reason = True
    db.commit()
    service = TimesheetService(db)
    at = NOW
    if action == "end-break":
        service.apply(context, "start-work", uuid4(), now_utc=NOW)
        service.apply(context, "start-break", uuid4(), now_utc=NOW)
        at += timedelta(hours=1)
    at = at.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=3)))
    assert service.get_status(context, at).late_reason_required is False
    assert service.apply(context, action, uuid4(), now_utc=at).status == "working"
    assert db.query(LatenessIncident).count() == 0


def test_legacy_command_without_hash_replays_only_original_empty_reason(scope):
    from dataclasses import asdict

    db, context, _ = scope
    service = TimesheetService(db)
    key = uuid4()
    snapshot = service.get_status(context, NOW)
    response = asdict(snapshot)
    for field in (
        "late_reason_required",
        "late_reason_kind",
        "late_minutes",
        "break_sequence",
    ):
        response.pop(field)
    db.add(
        TimesheetCommand(
            account_id=10,
            amocrm_user_id=101,
            key=str(key),
            action="start-work",
            response=response,
        )
    )
    db.commit()
    assert (
        service.apply(context, "start-work", key, reason=" \n", now_utc=NOW) == snapshot
    )
    with pytest.raises(TimesheetConflict, match="IDEMPOTENCY_KEY_REUSED"):
        service.apply(context, "start-work", key, reason="new reason", now_utc=NOW)


def test_break_lateness_uses_latest_break_start_and_refuses_foreign_scope(scope):
    from app.services.lateness_service import LatenessService

    db, context, group = scope
    service = TimesheetService(db)
    service.apply(context, "start-work", uuid4(), now_utc=NOW)
    service.apply(context, "start-break", uuid4(), now_utc=NOW)
    work = db.query(WorkSession).one()
    # An unrelated legacy transition must not replace the actual break start.
    db.add(
        StatusTransition(
            work_session_id=work.id,
            to_status="working",
            timestamp=NOW + timedelta(minutes=30),
        )
    )
    db.commit()
    decision = LatenessService(db).for_break_return(
        context, work, db.query(GroupMember).one(), group, NOW + timedelta(minutes=61)
    )
    assert decision.late_minutes == 1 and decision.sequence == 1
    work.amocrm_account_id = 11
    with pytest.raises(ValueError, match="ACCOUNT_SCOPE_INVALID"):
        LatenessService(db).for_break_return(
            context, work, db.query(GroupMember).one(), group, NOW
        )
    db.rollback()


def test_break_command_rolls_back_status_totals_incident_and_result(scope, monkeypatch):
    db, context, _ = scope
    service = TimesheetService(db)
    service.apply(context, "start-work", uuid4(), now_utc=NOW)
    service.apply(context, "start-break", uuid4(), now_utc=NOW)

    def fail_commit():
        db.flush()
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(RuntimeError):
        service.apply(
            context,
            "end-break",
            uuid4(),
            reason="bus",
            now_utc=NOW + timedelta(minutes=61),
        )
    work = db.query(WorkSession).one()
    assert work.current_status.value == "break" and work.total_break_time == 0
    assert db.query(StatusTransition).count() == db.query(TimesheetCommand).count() == 2
    assert db.query(LatenessIncident).count() == 0


def test_status_query_count_is_bounded_as_late_incidents_accumulate(scope):
    from sqlalchemy import event

    db, context, _ = scope
    service = TimesheetService(db)
    service.apply(context, "start-work", uuid4(), now_utc=NOW)
    counts = []
    statements = []

    def capture(connection, cursor, statement, parameters, orm_context, executemany):
        statements.append(statement.lower())

    for sequence in range(1, 4):
        at = NOW + timedelta(hours=2 * sequence)
        service.apply(context, "start-break", uuid4(), now_utc=at)
        statements.clear()
        event.listen(db.bind, "before_cursor_execute", capture)
        try:
            status = service.get_status(context, at + timedelta(minutes=61))
        finally:
            event.remove(db.bind, "before_cursor_execute", capture)
        assert status.late_minutes == 1 and status.break_sequence == sequence
        assert not any("lateness_incidents" in statement for statement in statements)
        counts.append(len(statements))
        service.apply(context, "end-break", uuid4(), now_utc=at + timedelta(minutes=61))
    assert counts[0] == counts[1] == counts[2] and counts[0] <= 7
