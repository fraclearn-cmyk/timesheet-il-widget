"""Bounded annual cleanup for normalized timesheet report data."""

from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.activity_event import ActivityEvent
from app.models.activity_interval import ActivityInterval
from app.models.activity_session import ActivitySession
from app.models.call_event import CallEvent
from app.models.crm_event import CrmEvent
from app.models.lateness_incident import LatenessIncident
from app.models.presence_batch import PresenceBatch
from app.models.report import Report
from app.models.status_transition import StatusTransition
from app.models.timesheet_command import TimesheetCommand
from app.models.work_comment import WorkComment
from app.models.work_session import WorkSession


REPORT_RETENTION_DAYS = 365


class ReportRetentionService:
    """Delete one deterministic batch while preserving the latest 365 dates."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _ids(query, model, batch_size: int) -> list[int]:
        return [row[0] for row in query.order_by(model.id).limit(batch_size).all()]

    def _delete_sessions(self, cutoff_date, cutoff_at, batch_size: int) -> int:
        ids = self._ids(
            self.db.query(WorkSession.id).filter(
                WorkSession.end_time.isnot(None),
                or_(
                    WorkSession.business_date < cutoff_date,
                    WorkSession.business_date.is_(None) & (WorkSession.end_time < cutoff_at),
                ),
            ),
            WorkSession,
            batch_size,
        )
        if not ids:
            return 0
        activity_ids = [
            row[0]
            for row in self.db.query(ActivitySession.id)
            .filter(ActivitySession.work_session_id.in_(ids))
            .all()
        ]
        if activity_ids:
            self.db.query(ActivityEvent).filter(
                ActivityEvent.activity_session_id.in_(activity_ids)
            ).delete(synchronize_session=False)
        self.db.query(ActivitySession).filter(
            ActivitySession.work_session_id.in_(ids)
        ).delete(synchronize_session=False)
        for model in (StatusTransition, ActivityInterval, LatenessIncident, WorkComment):
            self.db.query(model).filter(model.work_session_id.in_(ids)).delete(
                synchronize_session=False
            )
        self.db.query(WorkSession).filter(WorkSession.id.in_(ids)).delete(
            synchronize_session=False
        )
        return len(ids)

    def _delete_batch(self, model, timestamp, cutoff_at, batch_size: int, *extra) -> int:
        query = self.db.query(model.id).filter(timestamp < cutoff_at, *extra)
        ids = self._ids(query, model, batch_size)
        if ids:
            self.db.query(model).filter(model.id.in_(ids)).delete(
                synchronize_session=False
            )
        return len(ids)

    def cleanup(self, now: datetime, batch_size: int = 1000) -> int:
        if batch_size < 1:
            raise ValueError("report retention batch size must be positive")
        cutoff_date = now.date() - timedelta(days=REPORT_RETENTION_DAYS - 1)
        cutoff_at = datetime.combine(cutoff_date, datetime.min.time())

        deleted = self._delete_sessions(cutoff_date, cutoff_at, batch_size)
        if deleted:
            return deleted
        for model, timestamp, extra in (
            (CrmEvent, CrmEvent.occurred_at, ()),
            (CallEvent, CallEvent.occurred_at, ()),
            (
                ActivityInterval,
                ActivityInterval.ended_at,
                (
                    ActivityInterval.work_session_id.is_(None),
                    ActivityInterval.closed_at.isnot(None),
                ),
            ),
            (TimesheetCommand, TimesheetCommand.created_at, ()),
            (PresenceBatch, PresenceBatch.last_seen_at, ()),
            (Report, Report.end_date, ()),
        ):
            deleted = self._delete_batch(
                model, timestamp, cutoff_at, batch_size, *extra
            )
            if deleted:
                return deleted
        return 0

