from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum as SQLEnum,
    Boolean,
    Date,
    Index,
    text,
    ForeignKeyConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship
from app.core.time_utils import utc_now
import enum
from datetime import timezone
from app.core.database import Base


class WorkStatus(str, enum.Enum):
    """Work status enum"""

    WORKING = "working"
    BREAK = "break"
    FINISHED = "finished"


class WorkSession(Base):
    """Work session model - tracks employee work sessions"""

    __tablename__ = "work_sessions"
    __table_args__ = (
        CheckConstraint(
            "current_status IN ('working','break','finished')",
            name="ck_work_sessions_status",
        ),
        ForeignKeyConstraint(
            ["amocrm_account_id", "amocrm_user_id"],
            ["users.amocrm_account_id", "users.amocrm_user_id"],
            name="fk_work_sessions_amocrm_identity",
        ),
        CheckConstraint(
            "active_duration >= 0 AND unconfirmed_duration >= 0 AND break_duration >= 0 AND idle_duration >= 0",
            name="ck_work_sessions_durations",
        ),
        Index("uq_work_sessions_open_account_user", "amocrm_account_id", "amocrm_user_id", unique=True, postgresql_where=text("end_time IS NULL"), sqlite_where=text("end_time IS NULL")),
    )

    id = Column(Integer, primary_key=True, index=True)
    amocrm_user_id = Column(Integer, nullable=False, index=True)
    amocrm_account_id = Column(Integer, nullable=False, index=True)
    user = relationship("User")
    user_name = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)

    start_time = Column(DateTime, nullable=False, default=utc_now)
    end_time = Column(DateTime, nullable=True)
    business_date = Column(Date, nullable=True)

    current_status = Column(
        SQLEnum(
            WorkStatus,
            values_callable=lambda cls: [e.value for e in cls],
            native_enum=False,
            length=30,
        ),
        nullable=False,
        default=WorkStatus.WORKING,
    )

    # Calculated fields
    # Legacy elapsed counters are retained; they are NOT confirmed CRM work.
    total_work_time = Column(Integer, nullable=False, default=0, server_default="0")
    total_break_time = Column(Integer, nullable=False, default=0, server_default="0")
    break_count = Column(Integer, nullable=False, default=0, server_default="0")
    # Nonnegative whole seconds. Zero means no measured duration, never unknown.
    active_duration = Column(Integer, nullable=False, default=0, server_default="0")
    unconfirmed_duration = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    break_duration = Column(Integer, nullable=False, default=0, server_default="0")
    idle_duration = Column(Integer, nullable=False, default=0, server_default="0")

    # Late arrival tracking
    is_late = Column(Boolean, default=False)
    late_minutes = Column(Integer, nullable=True)  # Количество минут опоздания
    late_reason = Column(String(500), nullable=True)  # Причина опоздания

    # Forced finish tracking
    forced_finish = Column(Boolean, default=False)
    forced_finish_by = Column(Integer, nullable=True)  # User ID администратора
    forced_finish_reason = Column(String(500), nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    status_transitions = relationship(
        "StatusTransition", back_populates="work_session", cascade="all, delete-orphan"
    )
    activity_sessions = relationship(
        "ActivitySession", back_populates="work_session", cascade="all, delete-orphan"
    )
    activity_intervals = relationship(
        "ActivityInterval",
        back_populates="work_session",
        cascade="all, delete-orphan",
    )

    @staticmethod
    def _utc_naive(value):
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def contains_working_interval(self, started_at, ended_at):
        """Return whether the whole closed interval belongs to one WORKING span."""
        started_at = self._utc_naive(started_at)
        ended_at = self._utc_naive(ended_at)
        session_start = self._utc_naive(self.start_time)
        session_end = self._utc_naive(self.end_time) if self.end_time else None
        if ended_at < started_at or started_at < session_start:
            return False
        if session_end is not None and ended_at > session_end:
            return False

        transitions = sorted(
            self.status_transitions,
            key=lambda transition: self._utc_naive(transition.timestamp),
        )
        if not transitions:
            return self.current_status == WorkStatus.WORKING

        status = WorkStatus.WORKING.value
        for transition in transitions:
            timestamp = self._utc_naive(transition.timestamp)
            if timestamp <= started_at:
                status = transition.to_status
                continue
            if timestamp < ended_at and transition.to_status != WorkStatus.WORKING.value:
                return False
            if timestamp >= ended_at:
                break
        return status == WorkStatus.WORKING.value

    def __repr__(self):
        return f"<WorkSession(id={self.id}, amocrm_user_id={self.amocrm_user_id}, status={self.current_status})>"
