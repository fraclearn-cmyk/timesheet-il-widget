"""KPI calculation service"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta, date
from typing import Dict, List

from app.models.work_session import WorkSession
from app.models.user import User
from app.schemas.kpi import KPIMetrics, ChartData


class KPIService:
    """Service for calculating KPI metrics"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_user_kpi(self, user_id: int, amocrm_user_id: str) -> KPIMetrics:
        """Calculate KPI for a user"""
        now = datetime.now()
        today_start = datetime.combine(now.date(), datetime.min.time())
        week_start = today_start - timedelta(days=now.weekday())
        month_start = datetime(now.year, now.month, 1)
        
        # Today hours
        today_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == amocrm_user_id,
            WorkSession.start_time >= today_start
        ).all()
        hours_today = sum(s.total_work_time for s in today_sessions) / 3600
        
        # Week hours
        week_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == amocrm_user_id,
            WorkSession.start_time >= week_start
        ).all()
        hours_week = sum(s.total_work_time for s in week_sessions) / 3600
        
        # Month hours
        month_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == amocrm_user_id,
            WorkSession.start_time >= month_start
        ).all()
        hours_month = sum(s.total_work_time for s in month_sessions) / 3600
        
        # Average per day (month)
        days_in_month = (now - month_start).days + 1
        avg_hours = hours_month / days_in_month if days_in_month > 0 else 0
        
        # Late counts
        late_week = sum(1 for s in week_sessions if s.is_late)
        late_month = sum(1 for s in month_sessions if s.is_late)
        
        # Completion % (assuming 8h norm)
        completion = (avg_hours / 8) * 100 if avg_hours > 0 else 0
        
        # Current status
        current_session = self.db.query(WorkSession).filter(
            WorkSession.user_id == amocrm_user_id,
            WorkSession.end_time == None
        ).first()
        
        if current_session:
            status = current_session.status.value
            is_online = (now - current_session.last_activity).seconds < 300 if current_session.last_activity else False
        else:
            status = "offline"
            is_online = False
        
        return KPIMetrics(
            hours_today=round(hours_today, 2),
            hours_week=round(hours_week, 2),
            hours_month=round(hours_month, 2),
            avg_hours_per_day=round(avg_hours, 2),
            late_count_week=late_week,
            late_count_month=late_month,
            completion_percentage=round(completion, 1),
            current_status=status,
            is_online=is_online
        )
    
    def calculate_department_kpi(self, department_id: int) -> KPIMetrics:
        """Calculate KPI for a department"""
        now = datetime.now()
        today_start = datetime.combine(now.date(), datetime.min.time())
        week_start = today_start - timedelta(days=now.weekday())
        month_start = datetime(now.year, now.month, 1)
        
        # Get all users in department
        users = self.db.query(User).filter(User.department_id == department_id).all()
        user_ids = [u.amocrm_user_id for u in users]
        
        if not user_ids:
            return KPIMetrics(
                hours_today=0, hours_week=0, hours_month=0, avg_hours_per_day=0,
                late_count_week=0, late_count_month=0, completion_percentage=0,
                current_status="offline", is_online=False,
                total_employees=0, online_now=0
            )
        
        # Aggregate sessions
        week_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.start_time >= week_start
        ).all()
        
        month_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.start_time >= month_start
        ).all()
        
        today_sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.start_time >= today_start
        ).all()
        
        hours_today = sum(s.total_work_time for s in today_sessions) / 3600
        hours_week = sum(s.total_work_time for s in week_sessions) / 3600
        hours_month = sum(s.total_work_time for s in month_sessions) / 3600
        
        days_in_month = (now - month_start).days + 1
        avg_hours = hours_month / (len(users) * days_in_month) if users else 0
        
        late_week = sum(1 for s in week_sessions if s.is_late)
        late_month = sum(1 for s in month_sessions if s.is_late)
        
        completion = (avg_hours / 8) * 100 if avg_hours > 0 else 0
        
        # Online count
        online = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.end_time == None,
            WorkSession.last_activity >= now - timedelta(minutes=5)
        ).count()
        
        return KPIMetrics(
            hours_today=round(hours_today / len(users) if users else 0, 2),
            hours_week=round(hours_week / len(users) if users else 0, 2),
            hours_month=round(hours_month / len(users) if users else 0, 2),
            avg_hours_per_day=round(avg_hours, 2),
            late_count_week=late_week,
            late_count_month=late_month,
            completion_percentage=round(completion, 1),
            current_status="department",
            is_online=online > 0,
            total_employees=len(users),
            online_now=online
        )
    
    def get_chart_data(self, user_id: str, days: int = 7) -> ChartData:
        """Get chart data for user (last N days)"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # Get sessions for period
        sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id == user_id,
            WorkSession.start_time >= datetime.combine(start_date, datetime.min.time()),
            WorkSession.start_time <= datetime.combine(end_date, datetime.max.time())
        ).all()
        
        # Group by date
        data_by_date: Dict[date, float] = {}
        for session in sessions:
            session_date = session.start_time.date()
            hours = session.total_work_time / 3600
            data_by_date[session_date] = data_by_date.get(session_date, 0) + hours
        
        # Generate all dates in range
        labels = []
        values = []
        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime("%Y-%m-%d"))
            values.append(round(data_by_date.get(current_date, 0), 2))
            current_date += timedelta(days=1)
        
        # Chart.js format
        datasets = [{
            "label": "Рабочие часы",
            "data": values,
            "borderColor": "rgb(75, 192, 192)",
            "backgroundColor": "rgba(75, 192, 192, 0.2)",
            "tension": 0.1
        }]
        
        return ChartData(labels=labels, datasets=datasets)
    
    def get_department_chart_data(self, department_id: int, days: int = 7) -> ChartData:
        """Get chart data for department"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)
        
        # Get users
        users = self.db.query(User).filter(User.department_id == department_id).all()
        user_ids = [u.amocrm_user_id for u in users]
        
        if not user_ids:
            return ChartData(labels=[], datasets=[])
        
        # Get sessions
        sessions = self.db.query(WorkSession).filter(
            WorkSession.user_id.in_(user_ids),
            WorkSession.start_time >= datetime.combine(start_date, datetime.min.time()),
            WorkSession.start_time <= datetime.combine(end_date, datetime.max.time())
        ).all()
        
        # Group by date
        data_by_date: Dict[date, float] = {}
        for session in sessions:
            session_date = session.start_time.date()
            hours = session.total_work_time / 3600
            data_by_date[session_date] = data_by_date.get(session_date, 0) + hours
        
        # Generate labels and values
        labels = []
        values = []
        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime("%Y-%m-%d"))
            avg = data_by_date.get(current_date, 0) / len(users) if users else 0
            values.append(round(avg, 2))
            current_date += timedelta(days=1)
        
        datasets = [{
            "label": "Средние часы",
            "data": values,
            "borderColor": "rgb(54, 162, 235)",
            "backgroundColor": "rgba(54, 162, 235, 0.2)",
            "tension": 0.1
        }]
        
        return ChartData(labels=labels, datasets=datasets)
