from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.core.rbac import RBACService, get_rbac_service
from app.services.team_service import TeamService

router = APIRouter()


class TeamMemberStatus(BaseModel):
    """Team member status response"""
    user_id: int
    user_name: str
    department: str | None
    department_id: int | None
    current_status: str
    session_id: int | None
    session_start: datetime | None
    work_time: int
    break_time: int
    break_count: int
    last_activity: datetime | None
    last_activity_time: datetime | None  # Real CRM activity time
    is_online: bool  # Activity < 5 minutes


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
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    department_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    online_only: bool = Query(False),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get current status of team members with RBAC filtering.
    - Admin: all employees
    - ROP: only employees from allowed departments
    - Employee: forbidden
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can view team
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get accessible departments
    accessible_dept_ids = rbac.get_accessible_departments(user)
    
    service = TeamService(db)
    return service.get_team_status_with_rbac(
        accessible_dept_ids=accessible_dept_ids,
        department_id=department_id,
        status_filter=status_filter,
        online_only=online_only,
        search=search
    )


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


# Import team schemas
from app.schemas.team import (
    ActivityTimelineResponse,
    ActivityHistoryResponse,
    ForceFinishRequest,
    ForceFinishResponse
)


@router.get("/{target_user_id}/timeline", response_model=ActivityTimelineResponse)
def get_user_timeline(
    target_user_id: int,
    date: Optional[str] = Query(None),
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get user CRM activity timeline for specific date.
    Timeline shows 15-minute intervals with activity counts.
    Only ROP/Admin can view.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user or rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if user can view this employee
    from app.models.user import User
    target_user = db.query(User).filter(User.amocrm_user_id == target_user_id).first()
    
    if target_user and not rbac.can_view_employee(user, target_user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this employee"
        )
    
    service = TeamService(db)
    return service.get_user_timeline(target_user_id, date)


@router.get("/{target_user_id}/timeline/history", response_model=ActivityHistoryResponse)
def get_user_timeline_history(
    target_user_id: int,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get user CRM activity history for last 7 days.
    Only ROP/Admin can view.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user or rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if user can view this employee
    from app.models.user import User
    target_user = db.query(User).filter(User.amocrm_user_id == target_user_id).first()
    
    if target_user and not rbac.can_view_employee(user, target_user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this employee"
        )
    
    service = TeamService(db)
    return service.get_user_timeline_history(target_user_id)


@router.post("/{target_user_id}/force-finish", response_model=ForceFinishResponse)
def force_finish_session(
    target_user_id: int,
    request: ForceFinishRequest,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Force finish work session for employee.
    Only Admin can force finish.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not rbac.can_force_finish(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin can force finish sessions"
        )
    
    service = TeamService(db)
    return service.force_finish_session(
        target_user_id=target_user_id,
        admin_id=user.id,
        admin_name=user.name,
        reason=request.reason
    )
