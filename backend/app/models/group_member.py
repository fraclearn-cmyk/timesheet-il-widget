from app.core.time_utils import utc_now

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Index,
    ForeignKeyConstraint,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class GroupMember(Base):
    """Membership of an amoCRM user in one widget group."""

    __tablename__ = "group_members"
    __table_args__ = (
        Index(
            "uq_group_members_active_account_user",
            "account_id",
            "user_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active"),
        ),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["users.amocrm_account_id", "users.id"],
            name="fk_group_members_account_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["account_id", "group_id"],
            ["widget_groups.account_id", "widget_groups.id"],
            name="fk_group_members_account_group",
            ondelete="CASCADE",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    group_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)  # internal User.id
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    track_time = Column(Boolean, nullable=False, default=False)
    hide_widget = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    group = relationship("WidgetGroup", back_populates="members")
    user = relationship("User", overlaps="group,members")
