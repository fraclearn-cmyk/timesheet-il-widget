from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from app.models.work_session import WorkSession, WorkStatus


class TeamService:
    """Service for team monitoring"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_team_status(self, department: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get current status of all team members"""
        query = self.db.query(WorkSession)\
            .filter(WorkSession.current_status != WorkStatus.FINISHED)
        
        if department:
            query = query.filter(WorkSession.department == department)
        
        sessions = query.all()
        
        # Get unique users from all sessions (including finished today)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        all_users_query = self.db.query(
            WorkSession.user_id,
            WorkSession.user_name,
            WorkSession.department
        ).filter(WorkSession.start_time >= today_start)
        
        if department:
            all_users_query = all_users_query.filter(WorkSession.department == department)
        
        all_users = all_users_query.distinct().all()
        
        # Build status list
        status_list = []
        active_users = {s.user_id: s for s in sessions}
        
        for user_id, user_name, dept in all_users:
            if user_id in active_users:
                session = active_users[user_id]
                status_list.append({
                    "user_id": session.user_id,
                    "user_name": session.user_name,
                    "department": session.department,
                    "current_status": session.current_status.value,
                    "session_id": session.id,
                    "session_start": session.start_time,
                    "work_time": session.total_work_time,
                    "break_time": session.total_break_time,
                    "break_count": session.break_count,
                    "last_activity": session.updated_at
                })
            else:
                status_list.append({
                    "user_id": user_id,
                    "user_name": user_name,
                    "department": dept,
                    "current_status": "not_working",
                    "session_id": None,
                    "session_start": None,
                    "work_time": 0,
                    "break_time": 0,
                    "break_count": 0,
                    "last_activity": None
                })
        
        return status_list
    
    def get_team_stats(
        self, 
        department: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get team statistics"""
        if not date_from:
            date_from = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        if not date_to:
            date_to = datetime.utcnow()
        
        query = self.db.query(WorkSession)\
            .filter(
                and_(
                    WorkSession.start_time >= date_from,
                    WorkSession.start_time <= date_to
                )
            )
        
        if department:
            query = query.filter(WorkSession.department == department)
        
        sessions = query.all()
        
        # Calculate stats
        total_members = len(set(s.user_id for s in sessions))
        working = sum(1 for s in sessions if s.current_status == WorkStatus.WORKING)
        on_break = sum(1 for s in sessions if s.current_status == WorkStatus.BREAK)
        not_working = total_members - working - on_break
        
        total_work_time = sum(s.total_work_time for s in sessions)
        total_break_time = sum(s.total_break_time for s in sessions)
        
        avg_work_time = total_work_time / total_members if total_members > 0 else 0
        avg_break_time = total_break_time / total_members if total_members > 0 else 0
        
        return {
            "total_members": total_members,
            "working": working,
            "on_break": on_break,
            "not_working": not_working,
            "total_work_time": total_work_time,
            "total_break_time": total_break_time,
            "avg_work_time": round(avg_work_time, 2),
            "avg_break_time": round(avg_break_time, 2)
        }
    
    def get_team_activity(
        self, 
        date: datetime,
        department: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get team activity for specific date"""
        date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        date_end = date_start + timedelta(days=1)
        
        query = self.db.query(WorkSession)\
            .filter(
                and_(
                    WorkSession.start_time >= date_start,
                    WorkSession.start_time < date_end
                )
            )
        
        if department:
            query = query.filter(WorkSession.department == department)
        
        sessions = query.all()
        
        activity = []
        for session in sessions:
            activity.append({
                "user_id": session.user_id,
                "user_name": session.user_name,
                "department": session.department,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "status": session.current_status.value,
                "work_time": session.total_work_time,
                "break_time": session.total_break_time,
                "break_count": session.break_count
            })
        
        return activity
