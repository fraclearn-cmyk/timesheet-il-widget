from app.core.time_utils import utc_now

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    ForeignKeyConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class CallEvent(Base):
    """Normalized incoming or outgoing call from amoCRM analytics."""

    __tablename__ = "call_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["users.amocrm_account_id", "users.id"],
            name="fk_call_events_account_user",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_call_events_duration",
        ),
        CheckConstraint(
            "user_id IS NULL OR (author_amocrm_user_id IS NOT NULL AND author_amocrm_user_id > 0)",
            name="ck_call_events_author",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    source_event_id = Column(String(255), nullable=False, index=True)
    author_amocrm_user_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True, index=True)
    user = relationship("User")
    direction = Column(String(20), nullable=True)
    occurred_at = Column(DateTime, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=True)
    object_type = Column(String(50), nullable=True)
    object_id = Column(Integer, nullable=True)
    card_url = Column(String(1000), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
