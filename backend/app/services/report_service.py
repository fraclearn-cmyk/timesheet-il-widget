"""
Report Service
Сервис для генерации отчётов
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, extract
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
import json

from app.models.report import Report, ReportType, ReportFormat
from app.models.work_session import WorkSession, WorkStatus
from app.models.activity_session import ActivitySession
from app.models.activity_event import ActivityEvent
from app.schemas.report import (
    ReportGenerateRequest,
    DailyReportRequest,
    WeeklyReportRequest,
    MonthlyReportRequest,
    WorkSessionSummary,
    DailySummary,
    WeeklySummary,
    MonthlySummary,
    ActivitySummary,
    EmployeeReport,
    DepartmentReport,
    TimeStatistics,
    UserStatistics,
    PeriodStatistics
)


class ReportService:
    """Сервис отчётов"""
    
    @staticmethod
    def format_seconds(seconds: int) -> str:
        """Форматирование секунд в HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    @staticmethod
    def seconds_to_time_stats(seconds: int) -> TimeStatistics:
        """Конвертация секунд в TimeStatistics"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return TimeStatistics(
            total_seconds=seconds,
            hours=hours,
            minutes=minutes,
            formatted=ReportService.format_seconds(seconds)
        )
    
    @staticmethod
    def get_daily_report(
        db: Session,
        account_id: str,
        target_date: date,
        user_id: Optional[int] = None,
        department: Optional[str] = None
    ) -> DailySummary:
        """Получить дневной отчёт"""
        
        # Query filters
        filters = [
            WorkSession.account_id == account_id,
            func.date(WorkSession.start_time) == target_date
        ]
        
        if user_id:
            filters.append(WorkSession.user_id == user_id)
        if department:
            filters.append(WorkSession.department == department)
        
        # Get sessions
        sessions = db.query(WorkSession).filter(and_(*filters)).all()
        
        # Build summaries
        session_summaries = []
        total_work_time = 0
        total_break_time = 0
        
        for session in sessions:
            # Count activities
            activity_count = db.query(ActivitySession).filter(
                ActivitySession.work_session_id == session.id
            ).count()
            
            summary = WorkSessionSummary(
                session_id=session.id,
                user_id=session.user_id,
                user_name=session.user_name,
                date=session.start_time.date(),
                start_time=session.start_time,
                end_time=session.end_time,
                status=session.status.value,
                total_work_time=session.total_work_time,
                total_break_time=session.total_break_time,
                break_count=session.break_count,
                activity_count=activity_count
            )
            session_summaries.append(summary)
            
            total_work_time += session.total_work_time
            total_break_time += session.total_break_time
        
        total_users = len(set(s.user_id for s in sessions))
        average_work_time = total_work_time / total_users if total_users > 0 else 0
        
        return DailySummary(
            date=target_date,
            total_users=total_users,
            total_work_time=total_work_time,
            total_break_time=total_break_time,
            average_work_time=average_work_time,
            sessions=session_summaries
        )
    
    @staticmethod
    def get_weekly_report(
        db: Session,
        account_id: str,
        week_start: date,
        user_id: Optional[int] = None,
        department: Optional[str] = None
    ) -> WeeklySummary:
        """Получить недельный отчёт"""
        
        week_end = week_start + timedelta(days=6)
        
        # Get daily reports for each day
        daily_summaries = []
        total_work_time = 0
        total_break_time = 0
        all_users = set()
        
        current_date = week_start
        while current_date <= week_end:
            daily = ReportService.get_daily_report(
                db, account_id, current_date, user_id, department
            )
            daily_summaries.append(daily)
            
            total_work_time += daily.total_work_time
            total_break_time += daily.total_break_time
            for session in daily.sessions:
                all_users.add(session.user_id)
            
            current_date += timedelta(days=1)
        
        total_users = len(all_users)
        average_work_time = total_work_time / total_users if total_users > 0 else 0
        
        return WeeklySummary(
            week_start=week_start,
            week_end=week_end,
            total_users=total_users,
            total_work_time=total_work_time,
            total_break_time=total_break_time,
            average_work_time=average_work_time,
            days=daily_summaries
        )
    
    @staticmethod
    def get_monthly_report(
        db: Session,
        account_id: str,
        year: int,
        month: int,
        user_id: Optional[int] = None,
        department: Optional[str] = None
    ) -> MonthlySummary:
        """Получить месячный отчёт"""
        
        # Get first and last day of month
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
        
        # Get weekly reports
        weekly_summaries = []
        total_work_time = 0
        total_break_time = 0
        all_users = set()
        
        # Start from first Monday of month (or month start)
        current_date = month_start
        while current_date.weekday() != 0 and current_date > month_start - timedelta(days=7):
            current_date -= timedelta(days=1)
        
        while current_date <= month_end:
            weekly = ReportService.get_weekly_report(
                db, account_id, current_date, user_id, department
            )
            weekly_summaries.append(weekly)
            
            total_work_time += weekly.total_work_time
            total_break_time += weekly.total_break_time
            for day in weekly.days:
                for session in day.sessions:
                    all_users.add(session.user_id)
            
            current_date += timedelta(days=7)
        
        total_users = len(all_users)
        average_work_time = total_work_time / total_users if total_users > 0 else 0
        
        return MonthlySummary(
            year=year,
            month=month,
            total_users=total_users,
            total_work_time=total_work_time,
            total_break_time=total_break_time,
            average_work_time=average_work_time,
            weeks=weekly_summaries
        )
    
    @staticmethod
    def get_employee_report(
        db: Session,
        account_id: str,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> EmployeeReport:
        """Получить отчёт по сотруднику"""
        
        # Get user sessions
        sessions = db.query(WorkSession).filter(
            and_(
                WorkSession.account_id == account_id,
                WorkSession.user_id == user_id,
                func.date(WorkSession.start_time) >= start_date,
                func.date(WorkSession.start_time) <= end_date
            )
        ).all()
        
        if not sessions:
            return None
        
        # Build session summaries
        session_summaries = []
        total_work_time = 0
        total_break_time = 0
        days_worked = set()
        
        for session in sessions:
            activity_count = db.query(ActivitySession).filter(
                ActivitySession.work_session_id == session.id
            ).count()
            
            summary = WorkSessionSummary(
                session_id=session.id,
                user_id=session.user_id,
                user_name=session.user_name,
                date=session.start_time.date(),
                start_time=session.start_time,
                end_time=session.end_time,
                status=session.status.value,
                total_work_time=session.total_work_time,
                total_break_time=session.total_break_time,
                break_count=session.break_count,
                activity_count=activity_count
            )
            session_summaries.append(summary)
            
            total_work_time += session.total_work_time
            total_break_time += session.total_break_time
            days_worked.add(session.start_time.date())
        
        # Get activity statistics
        activities = db.query(
            ActivitySession.entity_type,
            func.count(ActivitySession.id).label('count'),
            func.sum(ActivitySession.duration).label('total_time')
        ).join(WorkSession).filter(
            and_(
                WorkSession.account_id == account_id,
                WorkSession.user_id == user_id,
                func.date(WorkSession.start_time) >= start_date,
                func.date(WorkSession.start_time) <= end_date
            )
        ).group_by(ActivitySession.entity_type).all()
        
        activity_summaries = []
        for activity in activities:
            event_count = db.query(ActivityEvent).join(ActivitySession).join(WorkSession).filter(
                and_(
                    WorkSession.user_id == user_id,
                    ActivitySession.entity_type == activity.entity_type
                )
            ).count()
            
            total_time = activity.total_time or 0
            avg_time = total_time / activity.count if activity.count > 0 else 0
            
            activity_summaries.append(ActivitySummary(
                entity_type=activity.entity_type,
                entity_count=activity.count,
                total_time=total_time,
                average_time=avg_time,
                event_count=event_count
            ))
        
        total_days_worked = len(days_worked)
        average_work_time = total_work_time / total_days_worked if total_days_worked > 0 else 0
        
        user_name = sessions[0].user_name
        department = sessions[0].department
        
        return EmployeeReport(
            user_id=user_id,
            user_name=user_name,
            department=department,
            period_start=start_date,
            period_end=end_date,
            total_days_worked=total_days_worked,
            total_work_time=total_work_time,
            total_break_time=total_break_time,
            average_work_time=average_work_time,
            sessions=session_summaries,
            activities=activity_summaries
        )
    
    @staticmethod
    def get_period_statistics(
        db: Session,
        account_id: str,
        start_date: date,
        end_date: date,
        department: Optional[str] = None
    ) -> PeriodStatistics:
        """Получить статистику за период"""
        
        filters = [
            WorkSession.account_id == account_id,
            func.date(WorkSession.start_time) >= start_date,
            func.date(WorkSession.start_time) <= end_date
        ]
        
        if department:
            filters.append(WorkSession.department == department)
        
        # Get all sessions
        sessions = db.query(WorkSession).filter(and_(*filters)).all()
        
        # Group by user
        users_data = {}
        for session in sessions:
            if session.user_id not in users_data:
                users_data[session.user_id] = {
                    'user_name': session.user_name,
                    'sessions': [],
                    'total_work_time': 0,
                    'total_break_time': 0
                }
            
            users_data[session.user_id]['sessions'].append(session)
            users_data[session.user_id]['total_work_time'] += session.total_work_time
            users_data[session.user_id]['total_break_time'] += session.total_break_time
        
        # Build user statistics
        user_statistics = []
        total_work_time = 0
        total_break_time = 0
        
        for user_id, data in users_data.items():
            sessions_count = len(data['sessions'])
            work_time = data['total_work_time']
            break_time = data['total_break_time']
            avg_day_time = work_time / sessions_count if sessions_count > 0 else 0
            
            # Get activities count
            activities_count = db.query(ActivitySession).join(WorkSession).filter(
                and_(
                    WorkSession.user_id == user_id,
                    WorkSession.account_id == account_id,
                    func.date(WorkSession.start_time) >= start_date,
                    func.date(WorkSession.start_time) <= end_date
                )
            ).count()
            
            # Get most active entity type
            most_active = db.query(
                ActivitySession.entity_type,
                func.count(ActivitySession.id).label('count')
            ).join(WorkSession).filter(
                and_(
                    WorkSession.user_id == user_id,
                    WorkSession.account_id == account_id
                )
            ).group_by(ActivitySession.entity_type).order_by(func.count(ActivitySession.id).desc()).first()
            
            user_stat = UserStatistics(
                user_id=user_id,
                user_name=data['user_name'],
                sessions_count=sessions_count,
                work_time=ReportService.seconds_to_time_stats(work_time),
                break_time=ReportService.seconds_to_time_stats(break_time),
                average_day_time=ReportService.seconds_to_time_stats(int(avg_day_time)),
                activities_count=activities_count,
                most_active_entity=most_active.entity_type if most_active else None
            )
            user_statistics.append(user_stat)
            
            total_work_time += work_time
            total_break_time += break_time
        
        return PeriodStatistics(
            start_date=start_date,
            end_date=end_date,
            total_users=len(users_data),
            total_sessions=len(sessions),
            work_time=ReportService.seconds_to_time_stats(total_work_time),
            break_time=ReportService.seconds_to_time_stats(total_break_time),
            users=user_statistics
        )
    
    @staticmethod
    def save_report(
        db: Session,
        account_id: str,
        report_type: ReportType,
        report_format: ReportFormat,
        title: str,
        start_date: datetime,
        end_date: datetime,
        data: Dict[str, Any],
        generated_by: int,
        user_id: Optional[int] = None,
        department: Optional[str] = None,
        description: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None
    ) -> Report:
        """Сохранить отчёт в БД"""
        
        report = Report(
            report_type=report_type,
            report_format=report_format,
            title=title,
            description=description,
            start_date=start_date,
            end_date=end_date,
            account_id=account_id,
            user_id=user_id,
            department=department,
            data=data,
            summary=summary,
            file_path=file_path,
            file_size=file_size,
            generated_by=generated_by
        )
        
        db.add(report)
        db.commit()
        db.refresh(report)
        
        return report
    
    @staticmethod
    def get_reports(
        db: Session,
        account_id: str,
        skip: int = 0,
        limit: int = 100,
        report_type: Optional[ReportType] = None
    ) -> List[Report]:
        """Получить список отчётов"""
        
        query = db.query(Report).filter(Report.account_id == account_id)
        
        if report_type:
            query = query.filter(Report.report_type == report_type)
        
        return query.order_by(Report.generated_at.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_report_by_id(db: Session, report_id: int) -> Optional[Report]:
        """Получить отчёт по ID"""
        return db.query(Report).filter(Report.id == report_id).first()
    
    @staticmethod
    def delete_report(db: Session, report_id: int) -> bool:
        """Удалить отчёт"""
        report = db.query(Report).filter(Report.id == report_id).first()
        if report:
            db.delete(report)
            db.commit()
            return True
        return False
