from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class WorkComment(Base):
    """Work Comment model - comments from ROP/Admin on work sessions"""
    __tablename__ = "work_comments"

    id = Column(Integer, primary_key=True, index=True)
    work_session_id = Column(Integer, ForeignKey("work_sessions.id", ondelete="CASCADE"), nullable=False)
    
    author_id = Column(Integer, nullable=False)  # User ID РОП или Администратора
    author_name = Column(String(255), nullable=False)
    
    comment = Column(Text, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<WorkComment(id={self.id}, session={self.work_session_id}, author={self.author_name})>"
