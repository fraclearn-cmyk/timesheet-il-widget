from datetime import datetime, time

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Time
from sqlalchemy.orm import relationship

from app.core.database import Base


class WidgetGroup(Base):
    """Independent employee group configured inside the widget."""

    __tablename__ = "widget_groups"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    timezone = Column(String(64), nullable=False, default="UTC")
    work_start_time = Column(Time, nullable=False, default=time(9, 0))
    work_end_time = Column(Time, nullable=False, default=time(18, 0))
    manager_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = relationship("User", foreign_keys=[manager_user_id])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
