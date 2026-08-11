from sqlalchemy import Column, Integer, String, Time, Boolean, DateTime
from datetime import datetime
from app.core.database import Base


class Department(Base):
    """Department model - represents company departments with work schedule"""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    
    # Work schedule
    work_start_time = Column(Time, nullable=False)  # Например: 09:00:00
    work_end_time = Column(Time, nullable=False)    # Например: 18:00:00
    
    # Settings
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Department(id={self.id}, name={self.name}, schedule={self.work_start_time}-{self.work_end_time})>"
