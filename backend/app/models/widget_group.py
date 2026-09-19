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
from sqlalchemy.orm import relationship, validates

from app.core.database import Base


class WidgetGroup(Base):
    """Independent employee group configured inside the widget."""

    __tablename__ = "widget_groups"
    __table_args__ = (
        UniqueConstraint("account_id", "id", name="uq_widget_groups_account_id"),
        UniqueConstraint(
            "account_id", "name_key", name="uq_widget_groups_account_name_key"
        ),
        ForeignKeyConstraint(
            ["account_id", "manager_user_id"],
            ["users.amocrm_account_id", "users.id"],
            name="fk_widget_groups_account_manager",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    name_key = Column(String(255), nullable=False)
    timezone = Column(String(64), nullable=False, default="UTC")
    work_start_time = Column(Time, nullable=False, default=time(9, 0))
    work_end_time = Column(Time, nullable=False, default=time(18, 0))
    manager_user_id = Column(Integer, nullable=True)
    # Snapshot of the manager's observed amoCRM role at trusted assignment.
    # It is compared with the live role on every privileged request; role IDs
    # remain opaque and are never interpreted semantically.
    manager_role_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    allow_restart_session = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    manager = relationship("User")
    members = relationship(
        "GroupMember", back_populates="group", cascade="all, delete-orphan"
    )

    @validates("name")
    def _derive_name_key(self, _key: str, value: str) -> str:
        self.name_key = value.strip().casefold()
        return value

    @validates("name_key")
    def _normalize_name_key(self, _key: str, value: str) -> str:
        return value.strip().casefold()

    def assign_manager(self, manager) -> None:
        """Assign a manager and capture the currently observed role snapshot."""
        if manager.amocrm_account_id != self.account_id:
            raise ValueError("manager belongs to another account")
        if manager.amocrm_role_id is None:
            raise ValueError("manager lacks an observed amoCRM role snapshot")
        self.manager_user_id = manager.id
        self.manager_role_id = manager.amocrm_role_id
