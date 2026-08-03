from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from app.core.database import get_db
from app.services.session_service import SessionService
from app.schemas.work_session import (
    WorkSessionCreate,
    WorkSessionResponse,
    WorkSessionWithDetails
)

router = APIRouter()


@router.post("/start", response_model=WorkSessionResponse, status_code=201)
def start_session(
    data: WorkSessionCreate,
    db: Session = Depends(get_db)
):
    """Start new work session"""
    service = SessionService(db)
    try:
        session = service.start_session(data)
        return WorkSessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/break/{user_id}", response_model=WorkSessionResponse)
def take_break(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Take a break"""
    service = SessionService(db)
    try:
        session = service.take_break(user_id)
        return WorkSessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume/{user_id}", response_model=WorkSessionResponse)
def resume_work(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Resume work from break"""
    service = SessionService(db)
    try:
        session = service.resume_work(user_id)
        return WorkSessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/finish/{user_id}", response_model=WorkSessionResponse)
def finish_session(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Finish work session"""
    service = SessionService(db)
    try:
        session = service.finish_session(user_id)
        return WorkSessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/current/{user_id}", response_model=Optional[WorkSessionWithDetails])
def get_current_session(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user's current active session"""
    service = SessionService(db)
    session = service.get_current_session(user_id)
    
    if not session:
        return None
    
    return WorkSessionWithDetails.from_orm(session)


@router.get("/history/{user_id}", response_model=List[WorkSessionResponse])
def get_session_history(
    user_id: int,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get user's session history"""
    service = SessionService(db)
    sessions = service.get_session_history(user_id, date_from, date_to, limit)
    return [WorkSessionResponse.from_orm(s) for s in sessions]


@router.get("/{session_id}", response_model=WorkSessionWithDetails)
def get_session(
    session_id: int,
    db: Session = Depends(get_db)
):
    """Get session by ID with details"""
    service = SessionService(db)
    session = service.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return WorkSessionWithDetails.from_orm(session)
