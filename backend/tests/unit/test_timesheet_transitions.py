from datetime import datetime, timedelta, time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.access_policy import RequestContext
from app.core.database import Base
from app.models import GroupMember, StatusTransition, User, WidgetGroup, WorkSession
from app.services.timesheet_service import TimesheetConflict, TimesheetService


NOW = datetime(2026, 9, 22, 6)


@pytest.mark.parametrize('start,end,now,day,late', [
    (time(9), time(18), datetime(2026, 9, 22, 6), '2026-09-22', 0),
    (time(9), time(18), datetime(2026, 9, 22, 6, 17), '2026-09-22', 17),
    (time(22), time(6), datetime(2026, 9, 22, 19), '2026-09-22', 0),
    (time(22), time(6), datetime(2026, 9, 22, 22, 15), '2026-09-22', 195),
])
def test_start_work_persists_group_shift_lateness(scope, start, end, now, day, late):
    db, context, group = scope
    group.work_start_time, group.work_end_time = start, end
    db.commit()
    TimesheetService(db).apply(context, 'start-work', uuid4(), now)
    work = db.query(WorkSession).one()
    assert work.business_date.isoformat() == day
    assert work.start_time == now and work.start_time.tzinfo is None
    assert work.late_minutes == late
    assert work.is_late is (late > 0)


@pytest.fixture
def scope():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, amocrm_account_id=10, amocrm_user_id=101, name="One")
        group = WidgetGroup(id=1, account_id=10, name="Sales", timezone="Europe/Minsk")
        db.add_all([user, group])
        db.flush()
        db.add(GroupMember(account_id=10, user_id=1, group_id=1, is_active=True, track_time=True))
        db.commit()
        yield db, RequestContext(10, user), group
    engine.dispose()


def test_full_cycle_persists_history_and_utc_naive_times(scope):
    db, context, _ = scope
    service = TimesheetService(db)
    assert service.get_status(context, NOW).status == "not_started"
    snapshots = [service.apply(context, action, uuid4(), NOW + timedelta(minutes=i)) for i, action in enumerate(("start-work", "start-break", "end-break", "finish-work"))]
    assert [s.status for s in snapshots] == ["working", "on_break", "working", "finished"]
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
    first = service.apply(context, "start-work", key, NOW)
    assert service.apply(context, "start-work", key, NOW + timedelta(seconds=5)) == first
    assert db.query(StatusTransition).count() == 1
    with pytest.raises(TimesheetConflict, match="IDEMPOTENCY_KEY_REUSED"):
        service.apply(context, "start-break", key, NOW)


def test_invalid_transition_and_restart_permission(scope):
    db, context, group = scope
    service = TimesheetService(db)
    with pytest.raises(TimesheetConflict, match="STATUS_TRANSITION_INVALID"):
        service.apply(context, "start-break", uuid4(), NOW)
    service.apply(context, "start-work", uuid4(), NOW)
    service.apply(context, "finish-work", uuid4(), NOW + timedelta(minutes=1))
    with pytest.raises(TimesheetConflict, match="STATUS_TRANSITION_INVALID"):
        service.apply(context, "start-work", uuid4(), NOW + timedelta(minutes=2))
    group.allow_restart_session = True
    assert service.apply(context, "start-work", uuid4(), NOW + timedelta(minutes=2)).status == "working"
    assert db.query(WorkSession).count() == 2


def test_track_time_false_denies_commands(scope):
    db, context, _ = scope
    db.query(GroupMember).one().track_time = False
    db.commit()
    with pytest.raises(TimesheetConflict, match="TRACK_TIME_DISABLED"):
        TimesheetService(db).apply(context, "start-work", uuid4(), NOW)


def test_open_prior_business_day_remains_authoritative(scope):
    db, context, _ = scope
    service = TimesheetService(db)
    first = service.apply(context, "start-work", uuid4(), NOW)
    next_day = NOW + timedelta(days=1)
    assert service.get_status(context, next_day).session_id == first.session_id
    assert service.get_status(context, next_day).status == "working"
    with pytest.raises(TimesheetConflict, match="STATUS_TRANSITION_INVALID"):
        service.apply(context, "start-work", uuid4(), next_day)
    assert service.apply(context, "finish-work", uuid4(), next_day).status == "finished"


def test_account_identity_keeps_same_external_user_and_key_independent(scope):
    db, context, _ = scope
    other = User(id=2, amocrm_account_id=11, amocrm_user_id=101, name="Other")
    group = WidgetGroup(id=2, account_id=11, name="Other", timezone="UTC")
    db.add_all([other, group])
    db.flush()
    db.add(GroupMember(account_id=11, user_id=2, group_id=2, is_active=True, track_time=True))
    db.commit()
    key = uuid4()
    first = TimesheetService(db).apply(context, "start-work", key, NOW)
    second = TimesheetService(db).apply(RequestContext(11, other), "start-work", key, NOW)
    assert second.session_id != first.session_id
    assert db.query(StatusTransition).count() == 2
