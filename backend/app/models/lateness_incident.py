"""Account-scoped immutable facts about late starts and break returns."""

from enum import Enum

from sqlalchemy import (
    CheckConstraint, Column, DateTime, Enum as SQLEnum, ForeignKeyConstraint,
    Index, Integer, String, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.core.time_utils import utc_now


class LatenessKind(str, Enum):
    SHIFT_START = "shift_start"
    BREAK_RETURN = "break_return"


class LatenessIncident(Base):
    __tablename__ = "lateness_incidents"
    __table_args__ = (
        UniqueConstraint("work_session_id", "kind", "sequence", name="uq_lateness_incidents_session_kind_sequence"),
        ForeignKeyConstraint(
            ["account_id", "amocrm_user_id"],
            ["users.amocrm_account_id", "users.amocrm_user_id"],
            name="fk_lateness_incidents_account_user",
        ),
        ForeignKeyConstraint(
            ["account_id", "amocrm_user_id", "work_session_id"],
            ["work_sessions.amocrm_account_id", "work_sessions.amocrm_user_id", "work_sessions.id"],
            name="fk_lateness_incidents_account_user_session", ondelete="CASCADE",
        ),
        CheckConstraint("late_minutes > 0", name="ck_lateness_incidents_positive_minutes"),
        CheckConstraint(
            "(kind = 'shift_start' AND sequence = 0) OR (kind = 'break_return' AND sequence > 0)",
            name="ck_lateness_incidents_kind_sequence",
        ),
        CheckConstraint("reason IS NULL OR length(reason) <= 1000", name="ck_lateness_incidents_reason_length"),
        Index("ix_lateness_incidents_account_user_occurred_at", "account_id", "amocrm_user_id", "occurred_at"),
        Index("ix_lateness_incidents_account_session", "account_id", "work_session_id"),
    )

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, nullable=False)
    work_session_id = Column(Integer, nullable=False)
    amocrm_user_id = Column(Integer, nullable=False)
    kind = Column(SQLEnum(LatenessKind, values_callable=lambda cls: [item.value for item in cls], native_enum=False, length=30), nullable=False)
    sequence = Column(Integer, nullable=False)
    # UTC without tzinfo, matching work_sessions and status_transitions storage.
    occurred_at = Column(DateTime, nullable=False)
    late_minutes = Column(Integer, nullable=False)
    reason = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    work_session = relationship("WorkSession", back_populates="lateness_incidents")
