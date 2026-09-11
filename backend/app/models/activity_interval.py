from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class ActivityInterval(Base):
    """A visible timeline interval, confirmed by a CRM event or marked unconfirmed."""

    __tablename__ = "activity_intervals"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    work_session_id = Column(Integer, ForeignKey("work_sessions.id", ondelete="CASCADE"), nullable=True)
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=False, index=True)
    kind = Column(String(30), nullable=False)
    source = Column(String(30), nullable=False)
    duration_source = Column(String(30), nullable=False)
    event_type = Column(String(100), nullable=True)
    object_type = Column(String(50), nullable=True)
    object_id = Column(Integer, nullable=True)
    description = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")
    work_session = relationship("WorkSession")
