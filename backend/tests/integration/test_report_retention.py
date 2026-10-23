"""Annual retention of normalized timesheet and activity data."""

from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import (
    ActivityEvent,
    ActivityInterval,
    ActivitySession,
    CallEvent,
    CrmEvent,
    LatenessIncident,
    PresenceBatch,
    Report,
    StatusTransition,
    TimesheetCommand,
    User,
    WorkComment,
    WorkSession,
)
from app.services.report_retention_service import ReportRetentionService


NOW = datetime(2026, 10, 24, 12)


def database():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        User(id=1, amocrm_account_id=10, amocrm_user_id=101, name="A"),
        User(id=2, amocrm_account_id=11, amocrm_user_id=201, name="B"),
    ])
    db.commit()
    return db


def session(db, *, row_id, account=10, external=101, day, open_=False):
    row = WorkSession(
        id=row_id, amocrm_account_id=account, amocrm_user_id=external,
        user_name="Employee", business_date=day,
        start_time=datetime.combine(day, datetime.min.time()),
        end_time=None if open_ else datetime.combine(day, datetime.min.time()) + timedelta(hours=1),
        current_status="working" if open_ else "finished",
    )
    db.add(row)
    return row


def drain(service, *, batch_size=100):
    deleted = []
    while True:
        count = service.cleanup(NOW, batch_size=batch_size)
        service.db.commit()
        deleted.append(count)
        if count == 0:
            return deleted


def test_cleanup_keeps_exact_365_day_boundary_and_open_old_shift():
    db = database()
    old = session(db, row_id=10, day=date(2025, 10, 24))
    kept = session(db, row_id=11, day=date(2025, 10, 25))
    open_old = session(db, row_id=12, day=date(2024, 1, 1), open_=True)
    db.flush()
    activity = ActivitySession(work_session_id=old.id, entity_type="lead", entity_id=1)
    db.add(activity); db.flush()
    db.add_all([
        ActivityEvent(activity_session_id=activity.id, event_type="card_updated", timestamp=old.start_time),
        StatusTransition(work_session_id=old.id, from_status="working", to_status="finished", timestamp=old.end_time),
        ActivityInterval(account_id=10, user_id=1, work_session_id=old.id, started_at=old.start_time,
                         ended_at=old.end_time, kind="confirmed", source="crm_event", duration_source="calculated"),
        LatenessIncident(account_id=10, amocrm_user_id=101, work_session_id=old.id,
                         kind="shift_start", sequence=0, occurred_at=old.start_time, late_minutes=5, reason="reason"),
        WorkComment(work_session_id=old.id, author_id=1, author_name="Admin", comment="comment"),
    ])
    db.commit()
    old_id, kept_id, open_old_id = old.id, kept.id, open_old.id

    assert drain(ReportRetentionService(db))[0] == 1
    assert db.get(WorkSession, old_id) is None
    assert db.get(WorkSession, kept_id) is not None
    assert db.get(WorkSession, open_old_id) is not None
    assert db.query(StatusTransition).count() == 0
    assert db.query(ActivitySession).count() == 0
    assert db.query(ActivityEvent).count() == 0
    assert db.query(ActivityInterval).count() == 0
    assert db.query(LatenessIncident).count() == 0
    assert db.query(WorkComment).count() == 0


def test_cleanup_removes_old_normalized_rows_but_keeps_boundary_and_accounts_isolated():
    db = database()
    old_time = datetime(2025, 10, 24, 23, 59)
    keep_time = datetime(2025, 10, 25)
    for account, user_id, external in [(10, 1, 101), (11, 2, 201)]:
        db.add_all([
            CrmEvent(account_id=account, external_id=f"old-{account}", user_id=user_id,
                     author_amocrm_user_id=external, event_type="card_updated", occurred_at=old_time, is_complete=1),
            CrmEvent(account_id=account, external_id=f"keep-{account}", user_id=user_id,
                     author_amocrm_user_id=external, event_type="card_updated", occurred_at=keep_time, is_complete=1),
            CallEvent(account_id=account, source_event_id=f"old-call-{account}", user_id=user_id,
                      author_amocrm_user_id=external, direction="outgoing", duration_seconds=1,
                      occurred_at=old_time, is_complete=1),
            CallEvent(account_id=account, source_event_id=f"keep-call-{account}", user_id=user_id,
                      author_amocrm_user_id=external, direction="outgoing", duration_seconds=1,
                      occurred_at=keep_time, is_complete=1),
            TimesheetCommand(account_id=account, amocrm_user_id=external, key=str(uuid4()),
                             action="start_work", response={}, created_at=old_time),
            TimesheetCommand(account_id=account, amocrm_user_id=external, key=str(uuid4()),
                             action="start_work", response={}, created_at=keep_time),
            PresenceBatch(account_id=account, user_id=user_id, command_id=uuid4(),
                          window_started_at=old_time - timedelta(minutes=1), last_seen_at=old_time, signal_count=1),
            PresenceBatch(account_id=account, user_id=user_id, command_id=uuid4(),
                          window_started_at=keep_time, last_seen_at=keep_time, signal_count=1),
            ActivityInterval(account_id=account, user_id=user_id, work_session_id=None,
                             started_at=old_time - timedelta(minutes=1), ended_at=old_time,
                             closed_at=old_time, kind="unconfirmed", source="unconfirmed_input", duration_source="observed"),
            ActivityInterval(account_id=account, user_id=user_id, work_session_id=None,
                             started_at=old_time, ended_at=old_time, closed_at=None,
                             kind="unconfirmed", source="unconfirmed_input", duration_source="observed"),
            Report(report_type="daily", report_format="json", title="old", account_id=str(account),
                   data={}, generated_by=user_id, start_date=old_time, end_date=old_time),
            Report(report_type="daily", report_format="json", title="keep", account_id=str(account),
                   data={}, generated_by=user_id, start_date=keep_time, end_date=keep_time),
        ])
    db.commit()

    counts = drain(ReportRetentionService(db), batch_size=1)
    assert all(count in (0, 1) for count in counts)
    assert db.query(CrmEvent).count() == 2
    assert db.query(CallEvent).count() == 2
    assert db.query(TimesheetCommand).count() == 2
    assert db.query(PresenceBatch).count() == 2
    assert db.query(ActivityInterval).count() == 2  # boundary rows plus old rows still open
    assert db.query(Report).count() == 2
    assert {row.account_id for row in db.query(CrmEvent).all()} == {10, 11}
    assert drain(ReportRetentionService(db), batch_size=1) == [0]


def test_session_cleanup_is_bounded_and_repeatable():
    db = database()
    for row_id in range(20, 23):
        session(db, row_id=row_id, day=date(2025, 1, row_id - 19))
    db.commit()
    service = ReportRetentionService(db)
    assert drain(service, batch_size=1) == [1, 1, 1, 0]

