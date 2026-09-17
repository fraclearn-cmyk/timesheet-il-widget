from datetime import time
from app.core.time_utils import utc_now

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Time,
    UniqueConstraint,
    ForeignKeyConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class WidgetGroup(Base):
    """Independent employee group configured inside the widget."""

    __tablename__ = "widget_groups"
    __table_args__ = (
        UniqueConstraint("account_id", "id", name="uq_widget_groups_account_id"),
        ForeignKeyConstraint(
            ["account_id", "manager_user_id"],
            ["users.amocrm_account_id", "users.id"],
            name="fk_widget_groups_account_manager",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    timezone = Column(String(64), nullable=False, default="UTC")
    work_start_time = Column(Time, nullable=False, default=time(9, 0))
    work_end_time = Column(Time, nullable=False, default=time(18, 0))
    manager_user_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    manager = relationship("User")
    members = relationship(
        "GroupMember", back_populates="group", cascade="all, delete-orphan"
    )
