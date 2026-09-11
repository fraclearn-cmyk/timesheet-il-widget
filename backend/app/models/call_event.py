from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.core.database import Base


class CallEvent(Base):
    """Normalized incoming or outgoing call from amoCRM analytics."""

    __tablename__ = "call_events"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    source_event_id = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    direction = Column(String(20), nullable=False)
    occurred_at = Column(DateTime, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=True)
    object_type = Column(String(50), nullable=True)
    object_id = Column(Integer, nullable=True)
    card_url = Column(String(1000), nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
