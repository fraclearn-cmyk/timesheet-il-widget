from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class GroupMember(Base):
    """Membership of an amoCRM user in one widget group."""

    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("account_id", "user_id", name="uq_group_members_account_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("widget_groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    track_time = Column(Boolean, nullable=False, default=False)
    hide_widget = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("WidgetGroup", back_populates="members")
    user = relationship("User")
