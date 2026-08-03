from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
from typing import Optional, List
from app.models.work_session import WorkSession, WorkStatus
from app.models.status_transition import StatusTransition
from app.schemas.work_session import WorkSessionCreate, WorkSessionUpdate


class SessionService:
    """Service for managing work sessions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def start_session(self, data: WorkSessionCreate) -> WorkSession:
        """Start new work session"""
        # Check if user has active session
        active_session = self.get_current_session(data.user_id)
        if active_session:
            raise ValueError("User already has an active session")
        
        # Create new session
        session = WorkSession(
            user_id=data.user_id,
            user_name=data.user_name,
            department=data.department,
            start_time=datetime.utcnow(),
            current_status=WorkStatus.WORKING
        )
        self.db.add(session)
        self.db.flush()
        
        # Create initial status transition
        transition = StatusTransition(
            work_session_id=session.id,
            from_status=None,
            to_status=WorkStatus.WORKING.value,
            timestamp=session.start_time
        )
        self.db.add(transition)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def take_break(self, user_id: int) -> WorkSession:
        """Switch session to break status"""
        session = self.get_current_session(user_id)
        if not session:
            raise ValueError("No active session found")
        
        if session.current_status == WorkStatus.BREAK:
            raise ValueError("Already on break")
        
        if session.current_status == WorkStatus.FINISHED:
            raise ValueError("Session already finished")
        
        # Calculate work time
        last_transition = self.db.query(StatusTransition)\
            .filter(StatusTransition.work_session_id == session.id)\
            .order_by(StatusTransition.timestamp.desc())\
            .first()
        
        now = datetime.utcnow()
        if last_transition and session.current_status == WorkStatus.WORKING:
            work_duration = int((now - last_transition.timestamp).total_seconds())
            session.total_work_time += work_duration
        
        # Update status
        old_status = session.current_status
        session.current_status = WorkStatus.BREAK
        session.break_count += 1
        
        # Create transition
        transition = StatusTransition(
            work_session_id=session.id,
            from_status=old_status.value,
            to_status=WorkStatus.BREAK.value,
            timestamp=now,
            duration=work_duration if old_status == WorkStatus.WORKING else None
        )
        self.db.add(transition)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def resume_work(self, user_id: int) -> WorkSession:
        """Resume work from break"""
        session = self.get_current_session(user_id)
        if not session:
            raise ValueError("No active session found")
        
        if session.current_status != WorkStatus.BREAK:
            raise ValueError("Not on break")
        
        # Calculate break time
        last_transition = self.db.query(StatusTransition)\
            .filter(StatusTransition.work_session_id == session.id)\
            .order_by(StatusTransition.timestamp.desc())\
            .first()
        
        now = datetime.utcnow()
        if last_transition:
            break_duration = int((now - last_transition.timestamp).total_seconds())
            session.total_break_time += break_duration
        
        # Update status
        session.current_status = WorkStatus.WORKING
        
        # Create transition
        transition = StatusTransition(
            work_session_id=session.id,
            from_status=WorkStatus.BREAK.value,
            to_status=WorkStatus.WORKING.value,
            timestamp=now,
            duration=break_duration if last_transition else None
        )
        self.db.add(transition)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def finish_session(self, user_id: int) -> WorkSession:
        """Finish work session"""
        session = self.get_current_session(user_id)
        if not session:
            raise ValueError("No active session found")
        
        if session.current_status == WorkStatus.FINISHED:
            raise ValueError("Session already finished")
        
        # Calculate final time
        last_transition = self.db.query(StatusTransition)\
            .filter(StatusTransition.work_session_id == session.id)\
            .order_by(StatusTransition.timestamp.desc())\
            .first()
        
        now = datetime.utcnow()
        if last_transition:
            if session.current_status == WorkStatus.WORKING:
                work_duration = int((now - last_transition.timestamp).total_seconds())
                session.total_work_time += work_duration
            elif session.current_status == WorkStatus.BREAK:
                break_duration = int((now - last_transition.timestamp).total_seconds())
                session.total_break_time += break_duration
        
        # Update session
        old_status = session.current_status
        session.current_status = WorkStatus.FINISHED
        session.end_time = now
        
        # Create transition
        transition = StatusTransition(
            work_session_id=session.id,
            from_status=old_status.value,
            to_status=WorkStatus.FINISHED.value,
            timestamp=now
        )
        self.db.add(transition)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def get_current_session(self, user_id: int) -> Optional[WorkSession]:
        """Get user's current active session"""
        return self.db.query(WorkSession)\
            .filter(
                and_(
                    WorkSession.user_id == user_id,
                    WorkSession.current_status != WorkStatus.FINISHED
                )
            )\
            .first()
    
    def get_session_history(
        self, 
        user_id: int, 
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100
    ) -> List[WorkSession]:
        """Get user's session history"""
        query = self.db.query(WorkSession)\
            .filter(WorkSession.user_id == user_id)
        
        if date_from:
            query = query.filter(WorkSession.start_time >= date_from)
        
        if date_to:
            query = query.filter(WorkSession.start_time <= date_to)
        
        return query.order_by(WorkSession.start_time.desc())\
            .limit(limit)\
            .all()
    
    def get_session_by_id(self, session_id: int) -> Optional[WorkSession]:
        """Get session by ID"""
        return self.db.query(WorkSession)\
            .filter(WorkSession.id == session_id)\
            .first()
