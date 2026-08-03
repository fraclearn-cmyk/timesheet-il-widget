"""
Report Models
Модели для хранения сгенерированных отчётов
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum

from app.core.database import Base


class ReportType(str, enum.Enum):
    """Типы отчётов"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"
    EMPLOYEE = "employee"
    DEPARTMENT = "department"


class ReportFormat(str, enum.Enum):
    """Форматы отчётов"""
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"
    CSV = "csv"


class Report(Base):
    """Модель отчёта"""
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Report info
    report_type = Column(SQLEnum(ReportType), nullable=False, index=True)
    report_format = Column(SQLEnum(ReportFormat), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Period
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False, index=True)
    
    # Filters
    account_id = Column(String(100), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    department = Column(String(100), nullable=True, index=True)
    
    # Data
    data = Column(JSON, nullable=False)  # Report data as JSON
    summary = Column(JSON, nullable=True)  # Summary statistics
    
    # File
    file_path = Column(String(500), nullable=True)  # Path to generated file
    file_size = Column(Integer, nullable=True)  # File size in bytes
    
    # Metadata
    generated_by = Column(Integer, nullable=False)  # User who generated
    generated_at = Column(DateTime, nullable=False, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)  # When to delete
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Report {self.id}: {self.title} ({self.report_type})>"
