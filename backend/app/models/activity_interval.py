from datetime import timezone
from app.core.time_utils import utc_now

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    CheckConstraint,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ActivityInterval(Base):
    """A visible timeline interval, confirmed by a CRM event or marked unconfirmed."""

    __tablename__ = "activity_intervals"
    __table_args__ = (
        CheckConstraint("ended_at >= started_at", name="ck_activity_intervals_time"),
        CheckConstraint(
            "source IN ('crm_event','call','unconfirmed_input')",
            name="ck_activity_intervals_source",
        ),
        CheckConstraint(
            "(source = 'unconfirmed_input' AND kind = 'unconfirmed') OR (source IN ('crm_event','call') AND kind = 'confirmed' AND work_session_id IS NOT NULL)",
            name="ck_activity_intervals_kind",
        ),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["users.amocrm_account_id", "users.id"],
            name="fk_activity_intervals_account_user",
            ondelete="CASCADE",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    work_session_id = Column(
        Integer, ForeignKey("work_sessions.id", ondelete="CASCADE"), nullable=True
    )
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=False, index=True)
    kind = Column(String(30), nullable=False)
    source = Column(String(30), nullable=False)
    duration_source = Column(String(30), nullable=False)
    event_type = Column(String(100), nullable=True)
    object_type = Column(String(50), nullable=True)
    object_id = Column(Integer, nullable=True)
    description = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    user = relationship("User")
    work_session = relationship("WorkSession")

    @classmethod
    def from_evidence(cls, session, *, started_at, ended_at, source, evidence=None):
        """Create activity from server-resolved evidence, never browser claims.

        Storage uses naive UTC, matching the legacy schema. CRM windows are
        calculated; calls require a measured duration. This is not ingestion.
        """
        from app.models.work_session import WorkStatus
        from app.models.crm_event import CrmEvent
        from app.models.call_event import CallEvent

        def utc(value):
            if value.tzinfo is not None:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            return value

        started_at, ended_at = utc(started_at), utc(ended_at)
        if ended_at < started_at:
            raise ValueError("Interval ends before it starts")
        if source not in {"crm_event", "call", "unconfirmed_input"}:
            raise ValueError("Unsupported activity source")
        user = session.user
        if user is None or user.id is None or user.id <= 0:
            raise ValueError("Missing user attribution")
        if (
            user.amocrm_account_id != session.amocrm_account_id
            or user.amocrm_user_id != session.amocrm_user_id
        ):
            raise ValueError("Mismatched session attribution")
        confirmed = source != "unconfirmed_input"
        if confirmed:
            if session.current_status != WorkStatus.WORKING:
                raise ValueError("Confirmed intervals require WORKING status")
            if started_at < utc(session.start_time) or (
                session.end_time is not None and ended_at > utc(session.end_time)
            ):
                raise ValueError("Interval must stay inside a WORKING session")
            status = WorkStatus.WORKING.value
            for transition in sorted(
                session.status_transitions, key=lambda t: utc(t.timestamp)
            ):
                timestamp = utc(transition.timestamp)
                if timestamp <= started_at:
                    status = transition.to_status
                elif (
                    timestamp < ended_at and transition.to_status != WorkStatus.WORKING
                ):
                    raise ValueError("Interval crosses a non-WORKING transition")
            if status != WorkStatus.WORKING:
                raise ValueError("Interval starts outside WORKING")
            expected = CrmEvent if source == "crm_event" else CallEvent
            if not isinstance(evidence, expected):
                raise ValueError("Confirmed interval requires source evidence")
            if (
                evidence.user_id != user.id
                or evidence.account_id != session.amocrm_account_id
            ):
                raise ValueError("Evidence attribution does not match the session")
            if (
                evidence.author_amocrm_user_id is None
                or evidence.author_amocrm_user_id <= 0
                or evidence.author_amocrm_user_id != user.amocrm_user_id
            ):
                raise ValueError(
                    "External author attribution does not match the session"
                )
            if source == "crm_event" and not evidence.is_complete:
                raise ValueError("Incomplete CRM evidence")
            if source == "call" and (
                evidence.direction not in {"incoming", "outgoing"}
                or evidence.duration_seconds is None
                or evidence.duration_seconds < 0
                or (ended_at - started_at).total_seconds() != evidence.duration_seconds
            ):
                raise ValueError(
                    "Call interval requires measured call duration and direction"
                )
            if not started_at <= utc(evidence.occurred_at) <= ended_at:
                raise ValueError("Evidence timestamp outside interval")
        return cls(
            account_id=session.amocrm_account_id,
            user_id=user.id,
            work_session_id=session.id,
            started_at=started_at,
            ended_at=ended_at,
            kind="confirmed" if confirmed else "unconfirmed",
            source=source,
            duration_source="calculated" if source == "crm_event" else "observed",
            event_type=getattr(evidence, "event_type", None),
        )
