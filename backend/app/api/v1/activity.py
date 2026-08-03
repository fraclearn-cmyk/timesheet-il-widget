from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.core.database import get_db
from app.services.activity_service import ActivityService
from app.models.activity_session import EntityType
from app.models.activity_event import EventType
from app.schemas.activity_session import ActivitySessionResponse, ActivitySessionWithEvents
from app.schemas.activity_event import ActivityEventResponse

router = APIRouter()


@router.post("/start", response_model=ActivitySessionResponse, status_code=201)
def start_activity(
    work_session_id: int,
    entity_type: EntityType,
    entity_id: int,
    entity_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Start new activity session (открыть карточку)"""
    service = ActivityService(db)
    try:
        session = service.start_activity(work_session_id, entity_type, entity_id, entity_name)
        return ActivitySessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop/{activity_session_id}", response_model=ActivitySessionResponse)
def stop_activity(
    activity_session_id: int,
    db: Session = Depends(get_db)
):
    """Stop activity session (закрыть карточку)"""
    service = ActivityService(db)
    try:
        session = service.stop_activity(activity_session_id)
        return ActivitySessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/switch", response_model=ActivitySessionResponse)
def switch_activity(
    work_session_id: int,
    entity_type: EntityType,
    entity_id: int,
    entity_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Switch to another entity (переключиться на другую карточку)"""
    service = ActivityService(db)
    try:
        session = service.switch_activity(work_session_id, entity_type, entity_id, entity_name)
        return ActivitySessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/event", response_model=ActivityEventResponse, status_code=201)
def track_event(
    activity_session_id: int,
    event_type: EventType,
    description: Optional[str] = None,
    event_data: Optional[Dict[str, Any]] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Track event in activity session (зафиксировать событие)"""
    service = ActivityService(db)
    try:
        event = service.track_event(
            activity_session_id, event_type, event_data, description, category_id
        )
        return ActivityEventResponse.from_orm(event)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/current/{work_session_id}", response_model=Optional[ActivitySessionWithEvents])
def get_current_activity(
    work_session_id: int,
    db: Session = Depends(get_db)
):
    """Get current active activity session"""
    service = ActivityService(db)
    session = service.get_current_activity(work_session_id)
    
    if not session:
        return None
    
    return ActivitySessionWithEvents.from_orm(session)


@router.get("/history/{work_session_id}", response_model=List[ActivitySessionResponse])
def get_activity_history(
    work_session_id: int,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get activity history for work session"""
    service = ActivityService(db)
    sessions = service.get_activity_history(work_session_id, limit)
    return [ActivitySessionResponse.from_orm(s) for s in sessions]


@router.get("/events/{activity_session_id}", response_model=List[ActivityEventResponse])
def get_activity_events(
    activity_session_id: int,
    db: Session = Depends(get_db)
):
    """Get all events for activity session"""
    service = ActivityService(db)
    events = service.get_events(activity_session_id)
    return [ActivityEventResponse.from_orm(e) for e in events]


@router.get("/stats/{work_session_id}", response_model=Dict[str, Any])
def get_activity_stats(
    work_session_id: int,
    db: Session = Depends(get_db)
):
    """Get activity statistics for work session"""
    service = ActivityService(db)
    return service.get_activity_stats(work_session_id)
