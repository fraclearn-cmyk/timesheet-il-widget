from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum as SQLEnum,
    Boolean,
    UniqueConstraint,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship
from app.core.time_utils import utc_now
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    """User role enum"""

    EMPLOYEE = "employee"  # Обычный сотрудник
    ROP = "rop"  # Руководитель отдела продаж
    ADMIN = "admin"  # Администратор


class User(Base):
    """User model - represents amoCRM users with roles and permissions"""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "amocrm_account_id", "amocrm_user_id", name="uq_users_account_amocrm_user"
        ),
        UniqueConstraint(
            "amocrm_account_id", "id", name="uq_users_account_internal_id"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    amocrm_user_id = Column(Integer, nullable=False, index=True)
    amocrm_account_id = Column(Integer, nullable=False, index=True)

    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    avatar_url = Column(String(2048), nullable=True)
    amocrm_rights = Column(JSON, nullable=True)
    amocrm_role_id = Column(Integer, nullable=True)
    amocrm_group_id = Column(Integer, nullable=True)

    role = Column(
        SQLEnum(UserRole, values_callable=lambda cls: [e.value for e in cls]),
        nullable=False,
        default=UserRole.EMPLOYEE,
    )
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    department = relationship("Department")

    # Settings
    allow_restart_session = Column(
        Boolean, default=False
    )  # Разрешение повторного запуска в тот же день

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    rop_permissions = relationship(
        "RopPermission", back_populates="user", cascade="all, delete-orphan"
    )
    dashboard_settings = relationship(
        "DashboardSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<User(id={self.id}, amocrm_id={self.amocrm_user_id}, role={self.role})>"
        )
