"""Account-scoped, database-backed employee status commands."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_time import business_date
from app.core.time_utils import utc_now
from app.models import GroupMember, StatusTransition, TimesheetCommand, WidgetGroup, WorkSession, WorkStatus


class TimesheetConflict(ValueError):
    pass


@dataclass(frozen=True)
class TimesheetSnapshot:
    session_id: int | None
    status: str
    started_at: str | None
    ended_at: str | None
    break_seconds: int
    track_time: bool
    hide_widget: bool
    restart_allowed: bool


class TimesheetService:
    def __init__(self, db: Session):
        self.db = db

    def _membership(self, context):
        if context.user.amocrm_account_id != context.account_id:
            raise TimesheetConflict("ACCOUNT_SCOPE_INVALID")
        return (self.db.query(GroupMember, WidgetGroup)
                .join(WidgetGroup, (WidgetGroup.id == GroupMember.group_id) & (WidgetGroup.account_id == GroupMember.account_id))
                .filter(GroupMember.account_id == context.account_id, GroupMember.user_id == context.user.id,
                        GroupMember.is_active.is_(True), WidgetGroup.is_active.is_(True)).one_or_none())

    def _sessions(self, context, day):
        return (self.db.query(WorkSession)
                .filter(WorkSession.amocrm_account_id == context.account_id,
                        WorkSession.amocrm_user_id == context.user.amocrm_user_id,
                        WorkSession.business_date == day)
                .order_by(WorkSession.start_time.desc(), WorkSession.id.desc()).all())

    def _open_session(self, context):
        return (self.db.query(WorkSession)
                .filter(WorkSession.amocrm_account_id == context.account_id,
                        WorkSession.amocrm_user_id == context.user.amocrm_user_id,
                        WorkSession.end_time.is_(None))
                .one_or_none())

    def _snapshot(self, context, now, membership, preferred_work=None):
        if membership is None:
            return TimesheetSnapshot(None, "not_started", None, None, 0, False, False, False)
        member, group = membership
        day = business_date(now, group.timezone, group.work_start_time, group.work_end_time)
        sessions = self._sessions(context, day)
        open_session = self._open_session(context)
        work = preferred_work or open_session or (sessions[0] if sessions else None)
        if work is None:
            return TimesheetSnapshot(None, "not_started", None, None, 0, bool(member.track_time), bool(member.hide_widget), False)
        status = "on_break" if work.current_status == WorkStatus.BREAK else work.current_status.value
        break_seconds = int(work.total_break_time or 0)
        if status == "on_break":
            last = self.db.query(StatusTransition).filter(StatusTransition.work_session_id == work.id).order_by(StatusTransition.id.desc()).first()
            if last:
                break_seconds += max(0, int((now - last.timestamp).total_seconds()))
        return TimesheetSnapshot(work.id, status, work.start_time.isoformat() + "Z", work.end_time.isoformat() + "Z" if work.end_time else None,
                                 break_seconds, bool(member.track_time), bool(member.hide_widget), status == "finished" and bool(group.allow_restart_session))

    def get_status(self, context, now_utc=None):
        now = now_utc or utc_now()
        return self._snapshot(context, now, self._membership(context))

    def apply(self, context, action: str, key: UUID, now_utc=None):
        now = now_utc or utc_now()
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        if not isinstance(key, UUID):
            raise ValueError("idempotency key must be UUID")
        if action not in {"start-work", "start-break", "end-break", "finish-work"}:
            raise ValueError("unknown timesheet action")
        scope = (TimesheetCommand.account_id == context.account_id,
                 TimesheetCommand.amocrm_user_id == context.user.amocrm_user_id,
                 TimesheetCommand.key == str(key))
        previous = self.db.query(TimesheetCommand).filter(*scope).one_or_none()
        if previous:
            if previous.action != action:
                raise TimesheetConflict("IDEMPOTENCY_KEY_REUSED")
            return TimesheetSnapshot(**previous.response)
        try:
            # Lock the durable user row: distinct idempotency keys serialize too.
            from app.models import User
            self.db.query(User).filter(User.id == context.user.id, User.amocrm_account_id == context.account_id).with_for_update().one()
            previous = self.db.query(TimesheetCommand).filter(*scope).one_or_none()
            if previous:
                if previous.action != action:
                    raise TimesheetConflict("IDEMPOTENCY_KEY_REUSED")
                return TimesheetSnapshot(**previous.response)
            membership = self._membership(context)
            if membership is None or not membership[0].track_time:
                raise TimesheetConflict("TRACK_TIME_DISABLED")
            member, group = membership
            day = business_date(now, group.timezone, group.work_start_time, group.work_end_time)
            sessions = self._sessions(context, day)
            work = self._open_session(context)
            state = "on_break" if work and work.current_status == WorkStatus.BREAK else "working" if work else "finished" if sessions else "not_started"
            allowed = {"not_started": {"start-work"}, "working": {"start-break", "finish-work"}, "on_break": {"end-break", "finish-work"}, "finished": {"start-work"} if group.allow_restart_session else set()}
            if action not in allowed[state]:
                raise TimesheetConflict("STATUS_TRANSITION_INVALID")
            if action == "start-work":
                work = WorkSession(amocrm_account_id=context.account_id, amocrm_user_id=context.user.amocrm_user_id,
                                   user_name=context.user.name, start_time=now, business_date=day, current_status=WorkStatus.WORKING)
                self.db.add(work)
                self.db.flush()
                transition = StatusTransition(work_session_id=work.id, to_status="working", timestamp=now)
            else:
                target = {"start-break": WorkStatus.BREAK, "end-break": WorkStatus.WORKING, "finish-work": WorkStatus.FINISHED}[action]
                previous_status = work.current_status.value
                prior = self.db.query(StatusTransition).filter(StatusTransition.work_session_id == work.id).order_by(StatusTransition.id.desc()).first()
                elapsed = max(0, int((now - prior.timestamp).total_seconds())) if prior else 0
                if previous_status == "break":
                    work.total_break_time += elapsed
                if action == "start-break":
                    work.break_count += 1
                work.current_status = target
                if target == WorkStatus.FINISHED:
                    work.end_time = now
                transition = StatusTransition(work_session_id=work.id, from_status=previous_status, to_status=target.value, timestamp=now, duration=elapsed)
            self.db.add(transition)
            self.db.flush()
            result = self._snapshot(context, now, membership, work)
            self.db.add(TimesheetCommand(account_id=context.account_id, amocrm_user_id=context.user.amocrm_user_id,
                                         key=str(key), action=action, response=asdict(result)))
            self.db.commit()
            return result
        except IntegrityError:
            self.db.rollback()
            winner = self.db.query(TimesheetCommand).filter(*scope).one_or_none()
            if winner:
                if winner.action != action:
                    raise TimesheetConflict("IDEMPOTENCY_KEY_REUSED")
                return TimesheetSnapshot(**winner.response)
            raise TimesheetConflict("STATUS_TRANSITION_INVALID") from None
