from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
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

    id = Column(Integer, primary_key=True, index=True)
    amocrm_user_id = Column(Integer, unique=True, nullable=False, index=True)
    amocrm_account_id = Column(Integer, nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.EMPLOYEE)
    department_id = Column(Integer, nullable=True)  # Foreign key to departments
    
    # Settings
    allow_restart_session = Column(Boolean, default=False)  # Разрешение повторного запуска в тот же день
    
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    rop_permissions = relationship("RopPermission", back_populates="user", cascade="all, delete-orphan")
    dashboard_settings = relationship("DashboardSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, amocrm_id={self.amocrm_user_id}, role={self.role})>"
