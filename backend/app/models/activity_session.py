from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class EntityType(str, enum.Enum):
    """Entity type enum"""
    LEAD = "lead"
    CONTACT = "contact"
    COMPANY = "company"
    TASK = "task"


class ActivitySession(Base):
    """Activity session model - tracks work with amoCRM entities"""
    __tablename__ = "activity_sessions"

    id = Column(Integer, primary_key=True, index=True)
    work_session_id = Column(Integer, ForeignKey("work_sessions.id", ondelete="CASCADE"), nullable=False)
    
    entity_type = Column(SQLEnum(EntityType), nullable=False)
    entity_id = Column(Integer, nullable=False)
    entity_name = Column(String(500), nullable=True)
    
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    
    duration = Column(Integer, nullable=True)  # seconds
    
    # Activity tracking
    is_active = Column(Integer, default=1)  # 1 = active, 0 = paused/ended
    last_activity_time = Column(DateTime, default=datetime.utcnow)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    work_session = relationship("WorkSession", back_populates="activity_sessions")
    activity_events = relationship("ActivityEvent", back_populates="activity_session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ActivitySession(id={self.id}, {self.entity_type}:{self.entity_id})>"
