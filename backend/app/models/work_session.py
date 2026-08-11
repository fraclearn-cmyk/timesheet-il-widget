from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class WorkStatus(str, enum.Enum):
    """Work status enum"""
    WORKING = "working"
    BREAK = "break"
    FINISHED = "finished"


class WorkSession(Base):
    """Work session model - tracks employee work sessions"""
    __tablename__ = "work_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # amoCRM user ID
    user_name = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)
    
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    
    current_status = Column(SQLEnum(WorkStatus), nullable=False, default=WorkStatus.WORKING)
    
    # Calculated fields
    total_work_time = Column(Integer, default=0)  # seconds
    total_break_time = Column(Integer, default=0)  # seconds
    break_count = Column(Integer, default=0)
    
    # Late arrival tracking
    is_late = Column(Boolean, default=False)
    late_minutes = Column(Integer, nullable=True)  # Количество минут опоздания
    late_reason = Column(String(500), nullable=True)  # Причина опоздания
    
    # Forced finish tracking
    forced_finish = Column(Boolean, default=False)
    forced_finish_by = Column(Integer, nullable=True)  # User ID администратора
    forced_finish_reason = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    status_transitions = relationship("StatusTransition", back_populates="work_session", cascade="all, delete-orphan")
    activity_sessions = relationship("ActivitySession", back_populates="work_session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkSession(id={self.id}, user_id={self.user_id}, status={self.current_status})>"
