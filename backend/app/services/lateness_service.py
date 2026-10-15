"""Calculate account-scoped lateness and append facts in the caller's transaction."""

from dataclasses import dataclass
from datetime import timedelta
from math import ceil

from sqlalchemy.orm import Session

from app.core.business_time import business_date, shift_start_utc
from app.models import LatenessIncident, StatusTransition, WorkSession
from app.models.lateness_incident import LatenessKind


@dataclass(frozen=True)
class LatenessDecision:
    kind: LatenessKind
    sequence: int
    late_minutes: int
    reason_required: bool


class LatenessService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _check_scope(context, work=None):
        if context.user.amocrm_account_id != context.account_id or (
            work is not None
            and (
                work.amocrm_account_id != context.account_id
                or work.amocrm_user_id != context.user.amocrm_user_id
            )
        ):
            raise ValueError("ACCOUNT_SCOPE_INVALID")

    @staticmethod
    def _decision(kind, sequence, seconds, member):
        minutes = ceil(max(0, seconds) / 60)
        return LatenessDecision(
            kind, sequence, minutes, bool(minutes and member.require_late_reason)
        )

    def for_shift_start(self, context, member, group, now):
        self._check_scope(context)
        if (
            member.account_id != context.account_id
            or member.user_id != context.user.id
            or group.account_id != context.account_id
        ):
            raise ValueError("ACCOUNT_SCOPE_INVALID")
        day = business_date(
            now, group.timezone, group.work_start_time, group.work_end_time
        )
        start = shift_start_utc(day, group.timezone, group.work_start_time)
        return self._decision(
            LatenessKind.SHIFT_START, 0, (now - start).total_seconds(), member
        )

    def for_break_return(self, context, work, member, group, now):
        self._check_scope(context, work)
        if (
            member.account_id != context.account_id
            or member.user_id != context.user.id
            or group.account_id != context.account_id
        ):
            raise ValueError("ACCOUNT_SCOPE_INVALID")
        start = (
            self.db.query(StatusTransition)
            .join(WorkSession, WorkSession.id == StatusTransition.work_session_id)
            .filter(
                WorkSession.amocrm_account_id == context.account_id,
                WorkSession.amocrm_user_id == context.user.amocrm_user_id,
                WorkSession.id == work.id,
                StatusTransition.to_status == "break",
            )
            .order_by(StatusTransition.timestamp.desc(), StatusTransition.id.desc())
            .first()
        )
        # Historical sessions can lack a transition. Never invent lateness.
        seconds = (
            (
                now - start.timestamp - timedelta(minutes=group.break_limit_minutes)
            ).total_seconds()
            if start
            else 0
        )
        return self._decision(
            LatenessKind.BREAK_RETURN, work.break_count, seconds, member
        )

    def record(self, context, work, decision, reason, now):
        self._check_scope(context, work)
        if not decision.late_minutes:
            return None
        incident = LatenessIncident(
            account_id=context.account_id,
            amocrm_user_id=context.user.amocrm_user_id,
            work_session_id=work.id,
            kind=decision.kind,
            sequence=decision.sequence,
            occurred_at=now,
            late_minutes=decision.late_minutes,
            reason=reason,
        )
        self.db.add(incident)
        return incident
