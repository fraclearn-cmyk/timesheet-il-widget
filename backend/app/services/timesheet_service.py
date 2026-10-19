"""Account-scoped, database-backed employee status commands."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.business_time import business_date
from app.core.time_utils import utc_now
from app.models import (
    GroupMember,
    StatusTransition,
    TimesheetCommand,
    WidgetGroup,
    WorkSession,
    WorkStatus,
)
from app.services.activity_interval_service import ActivityIntervalService
from app.services.lateness_service import LatenessService


class TimesheetConflict(ValueError):
    def __init__(self, code, *, details=None):
        super().__init__(code)
        self.details = details


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
    late_reason_required: bool = False
    late_reason_kind: str | None = None
    late_minutes: int = 0
    break_sequence: int | None = None


class TimesheetService:
    def __init__(self, db: Session):
        self.db = db

    def _membership(self, context):
        if context.user.amocrm_account_id != context.account_id:
            raise TimesheetConflict("ACCOUNT_SCOPE_INVALID")
        return (
            self.db.query(GroupMember, WidgetGroup)
            .join(
                WidgetGroup,
                (WidgetGroup.id == GroupMember.group_id)
                & (WidgetGroup.account_id == GroupMember.account_id),
            )
            .filter(
                GroupMember.account_id == context.account_id,
                GroupMember.user_id == context.user.id,
                GroupMember.is_active.is_(True),
                WidgetGroup.is_active.is_(True),
            )
            .populate_existing()
            .one_or_none()
        )

    def _sessions(self, context, day):
        return (
            self.db.query(WorkSession)
            .filter(
                WorkSession.amocrm_account_id == context.account_id,
                WorkSession.amocrm_user_id == context.user.amocrm_user_id,
                WorkSession.business_date == day,
            )
            .order_by(WorkSession.start_time.desc(), WorkSession.id.desc())
            .populate_existing()
            .all()
        )

    def _open_session(self, context):
        return (
            self.db.query(WorkSession)
            .filter(
                WorkSession.amocrm_account_id == context.account_id,
                WorkSession.amocrm_user_id == context.user.amocrm_user_id,
                WorkSession.end_time.is_(None),
            )
            .populate_existing()
            .one_or_none()
        )

    def _lateness_fields(
        self, context, now, membership, work=None, restart_allowed=False
    ):
        member, group = membership
        decision = None
        if member.track_time:
            service = LatenessService(self.db)
            if work is None or (work.end_time is not None and restart_allowed):
                decision = service.for_shift_start(context, member, group, now)
            elif work.current_status == WorkStatus.BREAK:
                decision = service.for_break_return(context, work, member, group, now)
        if decision is None or not decision.late_minutes:
            return {}
        return {
            "late_reason_required": decision.reason_required,
            "late_reason_kind": decision.kind.value,
            "late_minutes": decision.late_minutes,
            "break_sequence": (
                decision.sequence if decision.kind.value == "break_return" else None
            ),
        }

    def _snapshot(self, context, now, membership, preferred_work=None):
        if membership is None:
            # Visibility remains independent when disabled tracking deactivates
            # the group membership during a settings save.
            return TimesheetSnapshot(
                None,
                "not_started",
                None,
                None,
                0,
                False,
                bool(context.user.hide_widget),
                False,
            )
        member, group = membership
        day = business_date(
            now, group.timezone, group.work_start_time, group.work_end_time
        )
        sessions = self._sessions(context, day)
        open_session = self._open_session(context)
        work = preferred_work or open_session or (sessions[0] if sessions else None)
        if work is None:
            return TimesheetSnapshot(
                None,
                "not_started",
                None,
                None,
                0,
                bool(member.track_time),
                bool(member.hide_widget),
                False,
                **self._lateness_fields(context, now, membership),
            )
        status = (
            "on_break"
            if work.current_status == WorkStatus.BREAK
            else work.current_status.value
        )
        restart_allowed = (
            status == "finished"
            and bool(group.allow_restart_session)
            and len(sessions) == 1
        )
        break_seconds = int(work.total_break_time or 0)
        if status == "on_break":
            last = (
                self.db.query(StatusTransition)
                .filter(StatusTransition.work_session_id == work.id)
                .order_by(StatusTransition.id.desc())
                .first()
            )
            if last:
                break_seconds += max(0, int((now - last.timestamp).total_seconds()))
        return TimesheetSnapshot(
            work.id,
            status,
            work.start_time.isoformat() + "Z",
            work.end_time.isoformat() + "Z" if work.end_time else None,
            break_seconds,
            bool(member.track_time),
            bool(member.hide_widget),
            restart_allowed,
            **self._lateness_fields(
                context, now, membership, work, restart_allowed=restart_allowed
            ),
        )

    def get_status(self, context, now_utc=None):
        now = now_utc or utc_now()
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        return self._snapshot(context, now, self._membership(context))

    def apply(self, context, action: str, key: UUID, reason=None, now_utc=None):
        now = now_utc or utc_now()
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        if not isinstance(key, UUID):
            raise ValueError("idempotency key must be UUID")
        if action not in {"start-work", "start-break", "end-break", "finish-work"}:
            raise ValueError("unknown timesheet action")
        if context.user.amocrm_account_id != context.account_id:
            raise TimesheetConflict("ACCOUNT_SCOPE_INVALID")
        if reason is not None and not isinstance(reason, str):
            raise TimesheetConflict("INVALID_REASON")
        reason = reason.strip() or None if reason is not None else None
        if reason is not None and len(reason) > 1000:
            raise TimesheetConflict("INVALID_REASON")
        request_hash = sha256(
            json.dumps(
                {"action": action, "reason": reason},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        def replay(command):
            # Old commands have no hash and accepted no explanation. Preserve
            # their original no-reason retries without accepting a new payload.
            if command.action != action or (
                command.request_hash != request_hash
                if command.request_hash
                else reason is not None
            ):
                raise TimesheetConflict("IDEMPOTENCY_KEY_REUSED")
            return TimesheetSnapshot(**command.response)

        scope = (
            TimesheetCommand.account_id == context.account_id,
            TimesheetCommand.amocrm_user_id == context.user.amocrm_user_id,
            TimesheetCommand.key == str(key),
        )
        previous = self.db.query(TimesheetCommand).filter(*scope).one_or_none()
        if previous:
            return replay(previous)
        try:
            # Lock the durable user row: distinct idempotency keys serialize too.
            from app.models import User

            self.db.query(User).filter(
                User.id == context.user.id, User.amocrm_account_id == context.account_id
            ).with_for_update().one()
            previous = self.db.query(TimesheetCommand).filter(*scope).one_or_none()
            if previous:
                return replay(previous)
            membership = self._membership(context)
            if membership is None or not membership[0].track_time:
                raise TimesheetConflict("TRACK_TIME_DISABLED")
            member, group = membership
            day = business_date(
                now, group.timezone, group.work_start_time, group.work_end_time
            )
            sessions = self._sessions(context, day)
            work = self._open_session(context)
            state = (
                "on_break"
                if work and work.current_status == WorkStatus.BREAK
                else "working" if work else "finished" if sessions else "not_started"
            )
            allowed = {
                "not_started": {"start-work"},
                "working": {"start-break", "finish-work"},
                "on_break": {"end-break", "finish-work"},
                "finished": (
                    {"start-work"}
                    if group.allow_restart_session and len(sessions) == 1
                    else set()
                ),
            }
            if action not in allowed[state]:
                raise TimesheetConflict("STATUS_TRANSITION_INVALID")
            lateness = LatenessService(self.db)
            decision = None
            if action == "start-work":
                decision = lateness.for_shift_start(context, member, group, now)
            elif action == "end-break":
                decision = lateness.for_break_return(context, work, member, group, now)
            if decision and decision.reason_required and reason is None:
                raise TimesheetConflict(
                    "LATE_REASON_REQUIRED",
                    details={
                        "kind": decision.kind.value,
                        "late_minutes": decision.late_minutes,
                        "sequence": decision.sequence,
                    },
                )
            if action == "start-work":
                late = decision.late_minutes
                work = WorkSession(
                    amocrm_account_id=context.account_id,
                    amocrm_user_id=context.user.amocrm_user_id,
                    user_name=context.user.name,
                    start_time=now,
                    business_date=day,
                    current_status=WorkStatus.WORKING,
                    is_late=late > 0,
                    late_minutes=late,
                    late_reason=reason if late else None,
                )
                self.db.add(work)
                self.db.flush()
                transition = StatusTransition(
                    work_session_id=work.id, to_status="working", timestamp=now
                )
            else:
                target = {
                    "start-break": WorkStatus.BREAK,
                    "end-break": WorkStatus.WORKING,
                    "finish-work": WorkStatus.FINISHED,
                }[action]
                previous_status = work.current_status.value
                prior = (
                    self.db.query(StatusTransition)
                    .filter(StatusTransition.work_session_id == work.id)
                    .order_by(StatusTransition.id.desc())
                    .first()
                )
                elapsed = (
                    max(0, int((now - prior.timestamp).total_seconds())) if prior else 0
                )
                if previous_status == "break":
                    work.total_break_time += elapsed
                if action == "start-break":
                    work.break_count += 1
                work.current_status = target
                if target == WorkStatus.FINISHED:
                    work.end_time = now
                transition = StatusTransition(
                    work_session_id=work.id,
                    from_status=previous_status,
                    to_status=target.value,
                    timestamp=now,
                    duration=elapsed,
                )
            self.db.add(transition)
            if decision:
                lateness.record(context, work, decision, reason, now)
            self.db.flush()
            if action in {"start-break", "finish-work"}:
                ActivityIntervalService(self.db).close_for_status_transition(
                    work, at=now
                )
            result = self._snapshot(context, now, membership, work)
            self.db.add(
                TimesheetCommand(
                    account_id=context.account_id,
                    amocrm_user_id=context.user.amocrm_user_id,
                    key=str(key),
                    action=action,
                    request_hash=request_hash,
                    response=asdict(result),
                )
            )
            self.db.commit()
            return result
        except IntegrityError:
            self.db.rollback()
            winner = self.db.query(TimesheetCommand).filter(*scope).one_or_none()
            if winner:
                return replay(winner)
            raise TimesheetConflict("STATUS_TRANSITION_INVALID") from None
        except Exception:
            self.db.rollback()
            raise
