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
    
    def get_team_status_with_rbac(
        self,
        accessible_dept_ids: Optional[List[int]],
        department_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        online_only: bool = False,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get team status with RBAC filtering.
        accessible_dept_ids: None = all (Admin), List = allowed (ROP), [] = none
        """
        from app.models.user import User
        from app.models.crm_activity import CRMActivity
        
        # Base query for users
        query = self.db.query(User).filter(User.is_active == True)
        
        # RBAC filtering by department
        if accessible_dept_ids is not None:  # Not Admin
            if not accessible_dept_ids:  # Empty list - no access
                return []
            query = query.filter(User.department_id.in_(accessible_dept_ids))
        
        # Filter by specific department
        if department_id:
            query = query.filter(User.department_id == department_id)
        
        # Search by name
        if search:
            query = query.filter(User.name.ilike(f"%{search}%"))
        
        users = query.all()
        
        # Get active sessions
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        sessions_query = self.db.query(WorkSession).filter(
            WorkSession.start_time >= today_start,
            WorkSession.current_status != WorkStatus.FINISHED
        )
        sessions = {s.user_id: s for s in sessions_query.all()}
        
        # Get last CRM activity (last 5 minutes for online check)
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
        
        status_list = []
        for user in users:
            session = sessions.get(user.amocrm_user_id)
            
            # Get last activity from CRM
            last_crm_activity = self.db.query(CRMActivity).filter(
                CRMActivity.user_id == user.amocrm_user_id
            ).order_by(CRMActivity.created_at.desc()).first()
            
            last_activity_time = last_crm_activity.created_at if last_crm_activity else None
            is_online = last_activity_time and last_activity_time >= five_min_ago
            
            # Online filter
            if online_only and not is_online:
                continue
            
            if session:
                current_status = session.current_status.value
                
                # Status filter
                if status_filter and current_status != status_filter:
                    continue
                
                status_list.append({
                    "user_id": user.amocrm_user_id,
                    "user_name": user.name,
                    "department": user.department.name if user.department else None,
                    "department_id": user.department_id,
                    "current_status": current_status,
                    "session_id": session.id,
                    "session_start": session.start_time,
                    "work_time": session.total_work_time,
                    "break_time": session.total_break_time,
                    "break_count": session.break_count,
                    "last_activity": session.updated_at,
                    "last_activity_time": last_activity_time,
                    "is_online": is_online
                })
            else:
                current_status = "not_working"
                
                # Status filter
                if status_filter and current_status != status_filter:
                    continue
                
                status_list.append({
                    "user_id": user.amocrm_user_id,
                    "user_name": user.name,
                    "department": user.department.name if user.department else None,
                    "department_id": user.department_id,
                    "current_status": current_status,
                    "session_id": None,
                    "session_start": None,
                    "work_time": 0,
                    "break_time": 0,
                    "break_count": 0,
                    "last_activity": None,
                    "last_activity_time": last_activity_time,
                    "is_online": is_online
                })
        
        return status_list
    
    def get_user_timeline(self, user_id: int, date: Optional[str] = None) -> Dict[str, Any]:
        """Get user CRM activity timeline for specific date"""
        from app.models.crm_activity import CRMActivity
        from app.models.user import User
        
        if not date:
            target_date = datetime.utcnow().date()
        else:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        
        date_start = datetime.combine(target_date, datetime.min.time())
        date_end = datetime.combine(target_date, datetime.max.time())
        
        # Get user
        user = self.db.query(User).filter(User.amocrm_user_id == user_id).first()
        user_name = user.name if user else f"User {user_id}"
        
        # Get CRM activities
        activities = self.db.query(CRMActivity).filter(
            CRMActivity.user_id == user_id,
            CRMActivity.created_at >= date_start,
            CRMActivity.created_at <= date_end
        ).all()
        
        # Create 15-minute intervals (96 intervals per day)
        intervals = []
        current_time = date_start
        
        for _ in range(96):  # 24 * 4 = 96 intervals
            interval_end = current_time + timedelta(minutes=15)
            
            # Count activities in this interval
            interval_activities = [a for a in activities 
                                 if current_time <= a.created_at < interval_end]
            
            deals = sum(1 for a in interval_activities if a.entity_type == 'lead')
            contacts = sum(1 for a in interval_activities if a.entity_type == 'contact')
            companies = sum(1 for a in interval_activities if a.entity_type == 'company')
            tasks = sum(1 for a in interval_activities if a.entity_type == 'task')
            calls = sum(1 for a in interval_activities if a.activity_type == 'call')
            
            intervals.append({
                "start_time": current_time.strftime("%H:%M"),
                "end_time": interval_end.strftime("%H:%M"),
                "deals": deals,
                "contacts": contacts,
                "companies": companies,
                "tasks": tasks,
                "calls": calls,
                "total_events": len(interval_activities)
            })
            
            current_time = interval_end
        
        return {
            "user_id": user_id,
            "user_name": user_name,
            "date": target_date.strftime("%Y-%m-%d"),
            "intervals": intervals,
            "total_events": len(activities)
        }
    
    def get_user_timeline_history(self, user_id: int) -> Dict[str, Any]:
        """Get user CRM activity history for last 7 days"""
        from app.models.crm_activity import CRMActivity
        from app.models.user import User
        
        user = self.db.query(User).filter(User.amocrm_user_id == user_id).first()
        user_name = user.name if user else f"User {user_id}"
        
        days = []
        for i in range(7):
            target_date = datetime.utcnow().date() - timedelta(days=i)
            date_start = datetime.combine(target_date, datetime.min.time())
            date_end = datetime.combine(target_date, datetime.max.time())
            
            activities = self.db.query(CRMActivity).filter(
                CRMActivity.user_id == user_id,
                CRMActivity.created_at >= date_start,
                CRMActivity.created_at <= date_end
            ).all()
            
            deals = sum(1 for a in activities if a.entity_type == 'lead')
            contacts = sum(1 for a in activities if a.entity_type == 'contact')
            companies = sum(1 for a in activities if a.entity_type == 'company')
            tasks = sum(1 for a in activities if a.entity_type == 'task')
            calls = sum(1 for a in activities if a.activity_type == 'call')
            
            days.append({
                "date": target_date.strftime("%Y-%m-%d"),
                "total_events": len(activities),
                "deals": deals,
                "contacts": contacts,
                "companies": companies,
                "tasks": tasks,
                "calls": calls
            })
        
        return {
            "user_id": user_id,
            "user_name": user_name,
            "days": days
        }
    
    def force_finish_session(
        self,
        target_user_id: int,
        admin_id: int,
        admin_name: str,
        reason: str
    ) -> Dict[str, Any]:
        """Force finish work session for employee"""
        # Find active session
        session = self.db.query(WorkSession).filter(
            WorkSession.user_id == target_user_id,
            WorkSession.current_status != WorkStatus.FINISHED
        ).first()
        
        if not session:
            return {
                "success": False,
                "message": "No active session found",
                "session_id": 0
            }
        
        # Calculate total time
        now = datetime.utcnow()
        if session.current_status == WorkStatus.WORKING:
            session.total_work_time += int((now - session.last_status_change).total_seconds())
        elif session.current_status == WorkStatus.BREAK:
            session.total_break_time += int((now - session.last_status_change).total_seconds())
        
        # Update session
        session.current_status = WorkStatus.FINISHED
        session.end_time = now
        session.forced_finish = True
        session.forced_finish_by = admin_id
        session.forced_finish_reason = reason
        session.updated_at = now
        
        self.db.commit()
        self.db.refresh(session)
        
        return {
            "success": True,
            "message": f"Session force finished by {admin_name}",
            "session_id": session.id
        }
