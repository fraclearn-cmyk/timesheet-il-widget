"""
Report Schemas
Pydantic схемы для отчётов
"""
from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum


class ReportType(str, Enum):
    """Типы отчётов"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"
    EMPLOYEE = "employee"
    DEPARTMENT = "department"


class ReportFormat(str, Enum):
    """Форматы отчётов"""
    JSON = "json"
    EXCEL = "excel"
    PDF = "pdf"
    CSV = "csv"


# Request Schemas

class ReportGenerateRequest(BaseModel):
    """Запрос на генерацию отчёта"""
    report_type: ReportType
    report_format: ReportFormat = ReportFormat.JSON
    start_date: date
    end_date: date
    user_id: Optional[int] = None
    department: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_type": "daily",
                "report_format": "excel",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
                "user_id": 123,
                "department": "Продажи"
            }
        }


class DailyReportRequest(BaseModel):
    """Запрос дневного отчёта"""
    date: date
    user_id: Optional[int] = None
    department: Optional[str] = None


class WeeklyReportRequest(BaseModel):
    """Запрос недельного отчёта"""
    week_start: date
    user_id: Optional[int] = None
    department: Optional[str] = None


class MonthlyReportRequest(BaseModel):
    """Запрос месячного отчёта"""
    year: int
    month: int
    user_id: Optional[int] = None
    department: Optional[str] = None


# Response Schemas

class WorkSessionSummary(BaseModel):
    """Сводка по рабочей сессии"""
    session_id: int
    user_id: int
    user_name: str
    date: date
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    total_work_time: int  # seconds
    total_break_time: int  # seconds
    break_count: int
    activity_count: int


class DailySummary(BaseModel):
    """Дневная сводка"""
    date: date
    total_users: int
    total_work_time: int  # seconds
    total_break_time: int  # seconds
    average_work_time: float  # seconds
    sessions: List[WorkSessionSummary]


class WeeklySummary(BaseModel):
    """Недельная сводка"""
    week_start: date
    week_end: date
    total_users: int
    total_work_time: int
    total_break_time: int
    average_work_time: float
    days: List[DailySummary]


class MonthlySummary(BaseModel):
    """Месячная сводка"""
    year: int
    month: int
    total_users: int
    total_work_time: int
    total_break_time: int
    average_work_time: float
    weeks: List[WeeklySummary]


class ActivitySummary(BaseModel):
    """Сводка по активности"""
    entity_type: str
    entity_count: int
    total_time: int  # seconds
    average_time: float  # seconds
    event_count: int


class EmployeeReport(BaseModel):
    """Отчёт по сотруднику"""
    user_id: int
    user_name: str
    department: Optional[str]
    period_start: date
    period_end: date
    total_days_worked: int
    total_work_time: int
    total_break_time: int
    average_work_time: float
    sessions: List[WorkSessionSummary]
    activities: List[ActivitySummary]


class DepartmentReport(BaseModel):
    """Отчёт по отделу"""
    department: str
    period_start: date
    period_end: date
    total_employees: int
    total_work_time: int
    total_break_time: int
    average_work_time: float
    employees: List[EmployeeReport]


class ReportResponse(BaseModel):
    """Ответ с отчётом"""
    id: int
    report_type: ReportType
    report_format: ReportFormat
    title: str
    description: Optional[str]
    start_date: datetime
    end_date: datetime
    account_id: str
    user_id: Optional[int]
    department: Optional[str]
    data: Dict[str, Any]
    summary: Optional[Dict[str, Any]]
    file_path: Optional[str]
    file_size: Optional[int]
    generated_by: int
    generated_at: datetime
    
    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    """Список отчётов"""
    total: int
    reports: List[ReportResponse]


# Statistics Schemas

class TimeStatistics(BaseModel):
    """Статистика по времени"""
    total_seconds: int
    hours: int
    minutes: int
    formatted: str  # "HH:MM:SS"


class UserStatistics(BaseModel):
    """Статистика по пользователю"""
    user_id: int
    user_name: str
    sessions_count: int
    work_time: TimeStatistics
    break_time: TimeStatistics
    average_day_time: TimeStatistics
    activities_count: int
    most_active_entity: Optional[str]


class PeriodStatistics(BaseModel):
    """Статистика за период"""
    start_date: date
    end_date: date
    total_users: int
    total_sessions: int
    work_time: TimeStatistics
    break_time: TimeStatistics
    users: List[UserStatistics]
