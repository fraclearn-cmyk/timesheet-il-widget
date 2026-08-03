from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pydantic import BaseModel

from app.core.database import get_db
from app.services.team_service import TeamService

router = APIRouter()


class TeamMemberStatus(BaseModel):
    """Team member status response"""
    user_id: int
    user_name: str
    department: str | None
    current_status: str
    session_id: int | None
    session_start: datetime | None
    work_time: int
    break_time: int
    break_count: int
    last_activity: datetime | None


class TeamStats(BaseModel):
    """Team statistics response"""
    total_members: int
    working: int
    on_break: int
    not_working: int
    total_work_time: int
    total_break_time: int
    avg_work_time: float
    avg_break_time: float


@router.get("/status", response_model=List[TeamMemberStatus])
def get_team_status(
    department: str | None = Query(None),
    db: Session = Depends(get_db)
):
    """Get current status of all team members"""
    service = TeamService(db)
    return service.get_team_status(department)


@router.get("/stats", response_model=TeamStats)
def get_team_stats(
    department: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db)
):
    """Get team statistics"""
    service = TeamService(db)
    return service.get_team_stats(department, date_from, date_to)


@router.get("/activity", response_model=List[Dict[str, Any]])
def get_team_activity(
    date: datetime | None = Query(None),
    department: str | None = Query(None),
    db: Session = Depends(get_db)
):
    """Get team activity for specific date"""
    service = TeamService(db)
    if not date:
        date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    return service.get_team_activity(date, department)
