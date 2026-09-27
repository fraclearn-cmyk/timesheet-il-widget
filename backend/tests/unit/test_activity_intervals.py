"""Derived activity is bounded by authoritative WORKING history."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.access_policy import RequestContext
from app.models import (
    ActivityInterval,
    CallEvent,
    CrmEvent,
    GroupMember,
    PresenceBatch,
    StatusTransition,
    User,
    WidgetGroup,
    WorkSession,
    WorkStatus,
)
from app.services.activity_interval_service import ActivityIntervalService
from app.services.event_ingestion_service import EventIngestionService
from app.services.timesheet_service import TimesheetService


ACCOUNT_ID = 100
USER_ID = 7
AMOCRM_USER_ID = 700
START = datetime(2026, 9, 23, 8)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            User(
                id=USER_ID,
                amocrm_account_id=ACCOUNT_ID,
                amocrm_user_id=AMOCRM_USER_ID,
                name="Agent",
            )
        )
        session.commit()
        yield session
    engine.dispose()


def add_work_session(
    db: Session,
    *,
    start: datetime = START,
    end: datetime | None = None,
    status: WorkStatus = WorkStatus.WORKING,
    transitions: list[tuple[str, datetime]] | None = None,
) -> WorkSession:
    work = WorkSession(
        amocrm_account_id=ACCOUNT_ID,
        amocrm_user_id=AMOCRM_USER_ID,
        user_name="Agent",
        start_time=start,
        end_time=end,
        business_date=start.date(),
        current_status=status,
    )
    db.add(work)
    db.flush()
    for to_status, at in transitions or [("working", start)]:
        db.add(
            StatusTransition(
                work_session_id=work.id,
                to_status=to_status,
                timestamp=at,
            )
        )
    db.commit()
    return work


def crm_event(db: Session, *, at: datetime, **overrides) -> CrmEvent:
    values = {
        "account_id": ACCOUNT_ID,
        "external_id": f"event-{uuid4()}",
        "author_amocrm_user_id": AMOCRM_USER_ID,
        "user_id": USER_ID,
        "event_type": "lead_status_changed",
        "object_type": "lead",
        "object_id": 42,
        "occurred_at": at,
        "is_complete": 1,
    }
    values.update(overrides)
    event = CrmEvent(**values)
    if values["account_id"] == ACCOUNT_ID and values.get("user_id") == USER_ID:
        db.add(event)
        db.flush()
    return event


def call_event(db: Session, *, at: datetime, duration: int = 45, **overrides):
    values = {
        "account_id": ACCOUNT_ID,
        "source_event_id": f"call-{uuid4()}",
        "author_amocrm_user_id": AMOCRM_USER_ID,
        "user_id": USER_ID,
        "direction": "outgoing",
        "occurred_at": at,
        "duration_seconds": duration,
        "is_complete": 1,
    }
    values.update(overrides)
    event = CallEvent(**values)
    if values["account_id"] == ACCOUNT_ID and values.get("user_id") == USER_ID:
        db.add(event)
        db.flush()
    return event


def record(
    service: ActivityIntervalService,
    db: Session,
    *,
    started: datetime,
    seen: datetime,
    command_id: UUID | None = None,
    received: datetime | None = None,
):
    return service.record_presence(
        account_id=ACCOUNT_ID,
        user=db.get(User, USER_ID),
        command_id=command_id or uuid4(),
        window_started_at=started,
        last_seen_at=seen,
        signal_count=8,
        received_at=received or seen,
    )


def test_complete_crm_event_creates_a_zero_duration_confirmed_point(db):
    add_work_session(db)
    event = crm_event(db, at=START + timedelta(minutes=5))

    interval = ActivityIntervalService(db).attach_crm_event(event)

    assert interval is not None
    assert interval.started_at == interval.ended_at == event.occurred_at
    assert interval.kind == "confirmed"
    assert interval.source == "crm_event"
    assert interval.duration_source == "point"
    assert interval.work_session_id is not None


@pytest.mark.parametrize(
    "case",
    [
        "incomplete",
        "system",
        "foreign_account",
        "foreign_user",
        "before_start",
        "after_end",
        "during_break",
        "at_finish",
    ],
)
def test_untrusted_or_non_working_crm_evidence_creates_no_interval(db, case):
    other = User(
        id=8,
        amocrm_account_id=ACCOUNT_ID,
        amocrm_user_id=701,
        name="Other",
    )
    db.add(other)
    work = add_work_session(
        db,
        end=START + timedelta(hours=2),
        status=WorkStatus.FINISHED,
        transitions=[
            ("working", START),
            ("break", START + timedelta(minutes=30)),
            ("working", START + timedelta(minutes=40)),
            ("finished", START + timedelta(hours=2)),
        ],
    )
    at = START + timedelta(minutes=10)
    overrides = {}
    if case == "incomplete":
        overrides["is_complete"] = 0
    elif case == "system":
        overrides.update(author_amocrm_user_id=0, user_id=None)
    elif case == "foreign_account":
        overrides["account_id"] = ACCOUNT_ID + 1
    elif case == "foreign_user":
        overrides.update(user_id=8, author_amocrm_user_id=701)
    elif case == "before_start":
        at = START - timedelta(seconds=1)
    elif case == "after_end":
        at = work.end_time + timedelta(seconds=1)
    elif case == "during_break":
        at = START + timedelta(minutes=35)
    elif case == "at_finish":
        at = work.end_time

    interval = ActivityIntervalService(db).attach_crm_event(
        crm_event(db, at=at, **overrides)
    )

    assert interval is None
    assert db.query(ActivityInterval).count() == 0


def test_historical_working_segment_and_night_session_are_supported(db):
    start = datetime(2026, 9, 23, 21, 55)
    add_work_session(
        db,
        start=start,
        end=datetime(2026, 9, 24, 6),
        status=WorkStatus.FINISHED,
        transitions=[
            ("working", start),
            ("finished", datetime(2026, 9, 24, 6)),
        ],
    )
    event = crm_event(db, at=datetime(2026, 9, 24, 1, 15))

    assert ActivityIntervalService(db).attach_crm_event(event) is not None


def test_verified_call_uses_observed_duration_and_updates_active_union(db):
    work = add_work_session(db)
    service = ActivityIntervalService(db)
    first = service.attach_call(call_event(db, at=START + timedelta(minutes=1)))
    second = service.attach_call(
        call_event(db, at=START + timedelta(minutes=1, seconds=30), duration=45)
    )

    assert first is not None and second is not None
    assert first.ended_at - first.started_at == timedelta(seconds=45)
    assert first.duration_source == "observed"
    assert work.active_duration == 75


def test_call_crossing_break_or_without_measured_complete_evidence_is_ignored(db):
    add_work_session(
        db,
        status=WorkStatus.BREAK,
        transitions=[
            ("working", START),
            ("break", START + timedelta(seconds=30)),
        ],
    )
    service = ActivityIntervalService(db)

    assert service.attach_call(call_event(db, at=START + timedelta(seconds=10))) is None
    assert (
        service.attach_call(
            call_event(
                db,
                at=START + timedelta(seconds=1),
                duration=0,
                is_complete=0,
            )
        )
        is None
    )
    assert db.query(ActivityInterval).count() == 0


@pytest.mark.parametrize(
    "gap, expected_count",
    [(0, 1), (299, 1), (300, 1), (301, 2)],
)
def test_presence_merges_only_through_the_exact_five_minute_boundary(
    db, gap, expected_count
):
    add_work_session(db)
    service = ActivityIntervalService(db)
    record(
        service,
        db,
        started=START + timedelta(seconds=10),
        seen=START + timedelta(seconds=20),
    )

    interval = record(
        service,
        db,
        started=START + timedelta(seconds=20 + gap),
        seen=START + timedelta(seconds=30 + gap),
    )

    assert interval is not None
    assert db.query(ActivityInterval).count() == expected_count
    assert interval.ended_at == START + timedelta(seconds=30 + gap)


def test_presence_batch_spanning_break_is_stored_but_not_counted(db):
    work = add_work_session(
        db,
        status=WorkStatus.WORKING,
        transitions=[
            ("working", START),
            ("break", START + timedelta(minutes=5)),
            ("working", START + timedelta(minutes=6)),
        ],
    )

    interval = record(
        ActivityIntervalService(db),
        db,
        started=START + timedelta(minutes=4, seconds=50),
        seen=START + timedelta(minutes=6, seconds=10),
    )

    assert interval is None
    assert db.query(PresenceBatch).count() == 1
    assert db.query(ActivityInterval).count() == 0
    assert work.unconfirmed_duration == 0


def test_repeated_uuid_is_idempotent_and_out_of_order_packet_expands_safely(db):
    add_work_session(db)
    service = ActivityIntervalService(db)
    command_id = uuid4()
    first = record(
        service,
        db,
        command_id=command_id,
        started=START + timedelta(seconds=30),
        seen=START + timedelta(seconds=40),
    )
    replay = record(
        service,
        db,
        command_id=command_id,
        started=START + timedelta(seconds=30),
        seen=START + timedelta(seconds=40),
        received=START + timedelta(seconds=45),
    )
    earlier = record(
        service,
        db,
        started=START + timedelta(seconds=10),
        seen=START + timedelta(seconds=20),
        received=START + timedelta(seconds=50),
    )

    assert replay is first
    assert earlier is first
    assert first.started_at == START + timedelta(seconds=10)
    assert first.ended_at == START + timedelta(seconds=40)
    assert db.query(PresenceBatch).count() == 2
    assert db.query(ActivityInterval).count() == 1


def test_hidden_user_presence_is_recorded_without_identity_or_input_details(db):
    add_work_session(db)
    user = db.get(User, USER_ID)
    user.hide_widget = True

    interval = record(
        ActivityIntervalService(db),
        db,
        started=START + timedelta(seconds=10),
        seen=START + timedelta(seconds=50),
    )

    assert interval is not None
    assert interval.description is None
    assert interval.event_type is None
    assert interval.object_type is None
    assert interval.object_id is None


@pytest.mark.parametrize(
    "started,seen,received",
    [
        (START, START, START.replace(tzinfo=UTC)),
        (START + timedelta(seconds=2), START, START),
        (START, START + timedelta(seconds=1), START),
        (START, START + timedelta(seconds=61), START),
        (START, START, START + timedelta(minutes=10, seconds=1)),
    ],
)
def test_invalid_presence_timestamps_are_rejected(db, started, seen, received):
    add_work_session(db)

    with pytest.raises(ValueError, match="presence"):
        record(
            ActivityIntervalService(db),
            db,
            started=started,
            seen=seen,
            received=received,
        )

    assert db.query(PresenceBatch).count() == 0


def test_late_presence_after_finish_is_stored_but_cannot_create_activity(db):
    end = START + timedelta(minutes=5)
    add_work_session(
        db,
        end=end,
        status=WorkStatus.FINISHED,
        transitions=[("working", START), ("finished", end)],
    )

    interval = record(
        ActivityIntervalService(db),
        db,
        started=end + timedelta(seconds=1),
        seen=end + timedelta(seconds=2),
        received=end + timedelta(seconds=3),
    )

    assert interval is None
    assert db.query(PresenceBatch).count() == 1
    assert db.query(ActivityInterval).count() == 0


@pytest.mark.parametrize(
    "status, transition_status",
    [(WorkStatus.BREAK, "break"), (WorkStatus.FINISHED, "finished")],
)
def test_late_historical_presence_created_after_transition_is_closed(
    db, status, transition_status
):
    transition_at = START + timedelta(minutes=2)
    add_work_session(
        db,
        end=transition_at if status == WorkStatus.FINISHED else None,
        status=status,
        transitions=[("working", START), (transition_status, transition_at)],
    )

    interval = record(
        ActivityIntervalService(db),
        db,
        started=START + timedelta(seconds=20),
        seen=START + timedelta(seconds=40),
        received=transition_at + timedelta(seconds=1),
    )

    assert interval is not None
    assert interval.closed_at == transition_at
    assert interval.ended_at == START + timedelta(seconds=40)


@pytest.mark.parametrize(
    "status, transition_status",
    [(WorkStatus.BREAK, "break"), (WorkStatus.FINISHED, "finished")],
)
def test_late_historical_presence_cannot_reopen_transition_closed_interval(
    db, status, transition_status
):
    transition_at = START + timedelta(minutes=2)
    work = add_work_session(db)
    service = ActivityIntervalService(db)
    first = record(
        service,
        db,
        started=START + timedelta(seconds=10),
        seen=START + timedelta(seconds=30),
    )
    assert service.close_for_status_transition(work, at=transition_at) == 1
    work.current_status = status
    if status == WorkStatus.FINISHED:
        work.end_time = transition_at
    db.add(
        StatusTransition(
            work_session_id=work.id,
            from_status="working",
            to_status=transition_status,
            timestamp=transition_at,
        )
    )
    db.flush()

    merged = record(
        service,
        db,
        started=START + timedelta(seconds=40),
        seen=START + timedelta(seconds=50),
        received=transition_at + timedelta(seconds=1),
    )

    assert merged is first
    assert merged.closed_at == transition_at
    assert merged.ended_at == START + timedelta(seconds=50)


def test_server_closes_stale_presence_at_last_action_without_counting_wait(db):
    work = add_work_session(db)
    service = ActivityIntervalService(db)
    record(
        service,
        db,
        started=START,
        seen=START + timedelta(seconds=50),
    )

    assert service.close_stale_presence(now=START + timedelta(seconds=349)) == 0
    assert service.close_stale_presence(now=START + timedelta(seconds=350)) == 1
    assert service.close_stale_presence(now=START + timedelta(seconds=351)) == 0
    interval = db.query(ActivityInterval).one()
    assert interval.ended_at == START + timedelta(seconds=50)
    assert interval.closed_at == START + timedelta(seconds=350)
    assert interval.duration_source == "observed"
    assert work.unconfirmed_duration == 50


def test_status_transition_closure_never_extends_presence_to_transition_time(db):
    work = add_work_session(db)
    service = ActivityIntervalService(db)
    record(
        service,
        db,
        started=START,
        seen=START + timedelta(seconds=50),
    )

    assert service.close_for_status_transition(
        work, at=START + timedelta(minutes=2)
    ) == 1
    interval = db.query(ActivityInterval).one()
    assert interval.ended_at == START + timedelta(seconds=50)
    assert interval.closed_at == START + timedelta(minutes=2)
    assert service.close_for_status_transition(work, at=START + timedelta(minutes=2)) == 0


def test_status_transition_clamps_presence_observed_after_transition(db):
    work = add_work_session(db)
    service = ActivityIntervalService(db)
    record(
        service,
        db,
        started=START + timedelta(seconds=10),
        seen=START + timedelta(seconds=40),
        received=START + timedelta(seconds=40),
    )

    assert service.close_for_status_transition(
        work, at=START + timedelta(seconds=30)
    ) == 1
    interval = db.query(ActivityInterval).one()
    assert interval.started_at == START + timedelta(seconds=10)
    assert interval.ended_at == START + timedelta(seconds=30)
    assert interval.closed_at == START + timedelta(seconds=30)
    assert work.unconfirmed_duration == 20


def test_new_presence_reopens_closed_interval_only_when_it_extends_observation(db):
    add_work_session(db)
    service = ActivityIntervalService(db)
    first = record(service, db, started=START, seen=START + timedelta(seconds=50))
    assert service.close_stale_presence(now=START + timedelta(seconds=350)) == 1

    merged = record(
        service,
        db,
        started=START + timedelta(seconds=60),
        seen=START + timedelta(seconds=70),
        received=START + timedelta(seconds=71),
    )

    assert merged is first
    assert merged.closed_at is None
    assert service.close_stale_presence(now=START + timedelta(seconds=370)) == 1
    assert service.close_stale_presence(now=START + timedelta(seconds=371)) == 0


@pytest.mark.parametrize("action", ["start-break", "finish-work"])
def test_timesheet_transition_recomputes_presence_before_commit(db, action):
    user = db.get(User, USER_ID)
    group = WidgetGroup(
        id=1,
        account_id=ACCOUNT_ID,
        name="Sales",
        timezone="UTC",
    )
    db.add(group)
    db.flush()
    db.add(
        GroupMember(
            account_id=ACCOUNT_ID,
            user_id=USER_ID,
            group_id=group.id,
            track_time=True,
            is_active=True,
        )
    )
    db.commit()
    context = RequestContext(ACCOUNT_ID, user)
    timesheet = TimesheetService(db)
    timesheet.apply(context, "start-work", uuid4(), START)
    work = db.query(WorkSession).one()
    record(
        ActivityIntervalService(db),
        db,
        started=START,
        seen=START + timedelta(seconds=50),
    )
    work.unconfirmed_duration = 999
    db.flush()

    timesheet.apply(context, action, uuid4(), START + timedelta(minutes=2))

    assert work.unconfirmed_duration == 50


def test_ingestion_attaches_only_new_complete_normalized_evidence(db):
    at = START + timedelta(minutes=5)
    add_work_session(db)
    payload = {
        "id": "ingested-event",
        "type": "lead_status_changed",
        "created_at": int(at.replace(tzinfo=UTC).timestamp()),
        "created_by": AMOCRM_USER_ID,
        "account_id": ACCOUNT_ID,
        "entity_id": 42,
        "entity_type": "lead",
        "_links": {
            "self": {
                "href": "https://example.amocrm.ru/api/v4/events/ingested-event"
            }
        },
        "_embedded": {
            "account": {"id": ACCOUNT_ID},
            "entity": {
                "id": 42,
                "_links": {
                    "self": {"href": "https://example.amocrm.ru/api/v4/leads/42"}
                },
            },
        },
    }
    service = EventIngestionService(db, object(), object(), owner="test")

    with db.begin():
        first = service._persist_page(
            account_id=ACCOUNT_ID,
            account_url="https://example.amocrm.ru",
            known_types={"lead_status_changed"},
            items=[payload],
            now=at,
        )
    with db.begin():
        second = service._persist_page(
            account_id=ACCOUNT_ID,
            account_url="https://example.amocrm.ru",
            known_types={"lead_status_changed"},
            items=[payload],
            now=at + timedelta(minutes=1),
        )

    assert first.inserted == 1 and second.inserted == 0
    assert db.query(CrmEvent).count() == 1
    assert db.query(ActivityInterval).count() == 1


def test_unconfirmed_duration_excludes_overlap_with_measured_confirmed_work(db):
    work = add_work_session(db)
    service = ActivityIntervalService(db)
    record(
        service,
        db,
        started=START,
        seen=START + timedelta(seconds=60),
    )
    service.attach_call(call_event(db, at=START + timedelta(seconds=20), duration=20))

    assert work.active_duration == 20
    assert work.unconfirmed_duration == 40
