from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, UniqueConstraint

from app.core.database import Base


class CrmEvent(Base):
    """Normalized event received from amoCRM analytics."""

    __tablename__ = "crm_events"
    __table_args__ = (
        UniqueConstraint("account_id", "source_event_id", name="uq_crm_events_source_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    source_event_id = Column(String(255), nullable=False)
    user_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    object_type = Column(String(50), nullable=True)
    object_id = Column(Integer, nullable=True)
    occurred_at = Column(DateTime, nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    card_url = Column(String(1000), nullable=True)
    payload = Column(JSON, nullable=True)
    is_complete = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
