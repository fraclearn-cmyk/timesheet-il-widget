from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class EventType(str, enum.Enum):
    """Event type enum"""
    CALL_INCOMING = "call_incoming"
    CALL_OUTGOING = "call_outgoing"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    NOTE_ADDED = "note_added"
    EMAIL_SENT = "email_sent"
    EMAIL_RECEIVED = "email_received"
    CARD_OPENED = "card_opened"
    CARD_CLOSED = "card_closed"
    CARD_UPDATED = "card_updated"
    STATUS_CHANGED = "status_changed"


class ActivityEvent(Base):
    """Activity event model - tracks amoCRM events"""
    __tablename__ = "activity_events"

    id = Column(Integer, primary_key=True, index=True)
    activity_session_id = Column(Integer, ForeignKey("activity_sessions.id", ondelete="CASCADE"), nullable=False)
    
    event_type = Column(SQLEnum(EventType), nullable=False)
    event_data = Column(JSON, nullable=True)  # Additional event metadata
    
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Event details
    description = Column(String(1000), nullable=True)
    category_id = Column(Integer, ForeignKey("activity_categories.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    activity_session = relationship("ActivitySession", back_populates="activity_events")
    category = relationship("ActivityCategory", back_populates="events")

    def __repr__(self):
        return f"<ActivityEvent(id={self.id}, type={self.event_type})>"
