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
    Index,
    text,
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
            "duration_source IN ('point','observed','calculated')",
            name="ck_activity_intervals_duration_source",
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
        Index(
            "ix_activity_intervals_open_presence_end",
            "ended_at",
            "user_id",
            postgresql_where=text("source = 'unconfirmed_input' AND closed_at IS NULL"),
            sqlite_where=text("source = 'unconfirmed_input' AND closed_at IS NULL"),
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
    closed_at = Column(DateTime, nullable=True)

    user = relationship("User")
    work_session = relationship("WorkSession", back_populates="activity_intervals")

    @classmethod
    def from_evidence(cls, session, *, started_at, ended_at, source, evidence=None):
        """Create activity from server-resolved evidence, never browser claims.

        Storage uses naive UTC, matching the legacy schema. CRM windows are
        calculated; calls require a measured duration. This is not ingestion.
        """
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
        if not session.contains_working_interval(started_at, ended_at):
            raise ValueError("Interval must stay inside WORKING status")
        confirmed = source != "unconfirmed_input"
        if confirmed:
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
                not evidence.is_complete
                or evidence.direction not in {"incoming", "outgoing"}
                or evidence.duration_seconds is None
                or evidence.duration_seconds < 0
                or (ended_at - started_at).total_seconds() != evidence.duration_seconds
            ):
                raise ValueError(
                    "Call interval requires complete evidence with measured duration and direction"
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
            duration_source=(
                "point"
                if source == "crm_event" and started_at == ended_at
                else "calculated" if source == "crm_event" else "observed"
            ),
            event_type=getattr(evidence, "event_type", None),
            object_type=getattr(evidence, "object_type", None),
            object_id=getattr(evidence, "object_id", None),
            description=(
                getattr(evidence, "description", None)
                if source == "crm_event"
                else None
            ),
        )
