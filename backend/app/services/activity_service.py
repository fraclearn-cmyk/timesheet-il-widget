from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.models.activity_session import ActivitySession, EntityType
from app.models.activity_event import ActivityEvent, EventType
from app.models.activity_category import ActivityCategory
from app.models.work_session import WorkSession, WorkStatus
from app.schemas.activity_session import ActivitySessionCreate, ActivitySessionUpdate
from app.schemas.activity_event import ActivityEventCreate


class ActivityService:
    """Service for activity tracking"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def start_activity(
        self, 
        work_session_id: int,
        entity_type: EntityType,
        entity_id: int,
        entity_name: Optional[str] = None
    ) -> ActivitySession:
        """Start new activity session"""
        # Check if work session exists and is active
        work_session = self.db.query(WorkSession)\
            .filter(WorkSession.id == work_session_id)\
            .first()
        
        if not work_session:
            raise ValueError("Work session not found")
        
        if work_session.current_status == WorkStatus.FINISHED:
            raise ValueError("Work session is finished")
        
        # Pause current active sessions for this work session
        self.db.query(ActivitySession)\
            .filter(
                and_(
                    ActivitySession.work_session_id == work_session_id,
                    ActivitySession.is_active == 1
                )
            )\
            .update({
                "is_active": 0,
                "end_time": datetime.utcnow()
            })
        
        # Create new activity session
        now = datetime.utcnow()
        activity_session = ActivitySession(
            work_session_id=work_session_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            start_time=now,
            is_active=1,
            last_activity_time=now
        )
        
        self.db.add(activity_session)
        self.db.commit()
        self.db.refresh(activity_session)
        
        # Create initial event
        event = ActivityEvent(
            activity_session_id=activity_session.id,
            event_type=EventType.CARD_OPENED,
            timestamp=now,
            description=f"Opened {entity_type.value} #{entity_id}"
        )
        self.db.add(event)
        self.db.commit()
        
        return activity_session
    
    def stop_activity(self, activity_session_id: int) -> ActivitySession:
        """Stop activity session"""
        session = self.db.query(ActivitySession)\
            .filter(ActivitySession.id == activity_session_id)\
            .first()
        
        if not session:
            raise ValueError("Activity session not found")
        
        if session.is_active == 0:
            raise ValueError("Activity session already stopped")
        
        now = datetime.utcnow()
        duration = int((now - session.start_time).total_seconds())
        
        session.is_active = 0
        session.end_time = now
        session.duration = duration
        
        # Create close event
        event = ActivityEvent(
            activity_session_id=session.id,
            event_type=EventType.CARD_CLOSED,
            timestamp=now,
            description=f"Closed {session.entity_type.value} #{session.entity_id}"
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def switch_activity(
        self,
        work_session_id: int,
        entity_type: EntityType,
        entity_id: int,
        entity_name: Optional[str] = None
    ) -> ActivitySession:
        """Switch to another entity (stops current and starts new)"""
        # Stop current active session
        current_session = self.db.query(ActivitySession)\
            .filter(
                and_(
                    ActivitySession.work_session_id == work_session_id,
                    ActivitySession.is_active == 1
                )
            )\
            .first()
        
        if current_session:
            self.stop_activity(current_session.id)
        
        # Start new session
        return self.start_activity(work_session_id, entity_type, entity_id, entity_name)
    
    def track_event(
        self,
        activity_session_id: int,
        event_type: EventType,
        event_data: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        category_id: Optional[int] = None
    ) -> ActivityEvent:
        """Track an event in activity session"""
        session = self.db.query(ActivitySession)\
            .filter(ActivitySession.id == activity_session_id)\
            .first()
        
        if not session:
            raise ValueError("Activity session not found")
        
        now = datetime.utcnow()
        
        # Update last activity time
        session.last_activity_time = now
        
        # Create event
        event = ActivityEvent(
            activity_session_id=activity_session_id,
            event_type=event_type,
            event_data=event_data,
            timestamp=now,
            description=description,
            category_id=category_id
        )
        
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        
        return event
    
    def get_current_activity(self, work_session_id: int) -> Optional[ActivitySession]:
        """Get current active activity session"""
        return self.db.query(ActivitySession)\
            .filter(
                and_(
                    ActivitySession.work_session_id == work_session_id,
                    ActivitySession.is_active == 1
                )
            )\
            .first()
    
    def get_activity_history(
        self,
        work_session_id: int,
        limit: int = 100
    ) -> List[ActivitySession]:
        """Get activity history for work session"""
        return self.db.query(ActivitySession)\
            .filter(ActivitySession.work_session_id == work_session_id)\
            .order_by(desc(ActivitySession.start_time))\
            .limit(limit)\
            .all()
    
    def get_events(
        self,
        activity_session_id: int
    ) -> List[ActivityEvent]:
        """Get all events for activity session"""
        return self.db.query(ActivityEvent)\
            .filter(ActivityEvent.activity_session_id == activity_session_id)\
            .order_by(ActivityEvent.timestamp)\
            .all()
    
    def get_activity_stats(
        self,
        work_session_id: int
    ) -> Dict[str, Any]:
        """Get activity statistics for work session"""
        sessions = self.db.query(ActivitySession)\
            .filter(ActivitySession.work_session_id == work_session_id)\
            .all()
        
        if not sessions:
            return {
                "total_sessions": 0,
                "total_time": 0,
                "by_entity_type": {},
                "most_active": None
            }
        
        # Calculate stats
        total_time = sum(
            s.duration or int((datetime.utcnow() - s.start_time).total_seconds())
            for s in sessions
        )
        
        by_entity_type = {}
        for session in sessions:
            entity_type = session.entity_type.value
            if entity_type not in by_entity_type:
                by_entity_type[entity_type] = {
                    "count": 0,
                    "total_time": 0
                }
            by_entity_type[entity_type]["count"] += 1
            duration = session.duration or int((datetime.utcnow() - session.start_time).total_seconds())
            by_entity_type[entity_type]["total_time"] += duration
        
        # Find most active entity
        most_active_session = max(
            sessions,
            key=lambda s: s.duration or int((datetime.utcnow() - s.start_time).total_seconds())
        )
        
        return {
            "total_sessions": len(sessions),
            "total_time": total_time,
            "by_entity_type": by_entity_type,
            "most_active": {
                "entity_type": most_active_session.entity_type.value,
                "entity_id": most_active_session.entity_id,
                "entity_name": most_active_session.entity_name,
                "duration": most_active_session.duration or int(
                    (datetime.utcnow() - most_active_session.start_time).total_seconds()
                )
            }
        }
