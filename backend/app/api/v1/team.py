from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel

from app.core.database import get_db
from app.services.team_service import TeamService
from app.api.v1.dependencies import (
    APIProblem,
    RequestContext,
    get_request_context,
    not_found,
)
from app.core.access_policy import AccessPolicy
from app.schemas.team import (
    ActivityTimelineResponse,
    ActivityHistoryResponse,
    ActivityWindowResponse,
    ForceFinishRequest,
    ForceFinishResponse,
    TeamStatusResponse,
)
from app.services.team_service import ActivityRangeError
from app.core.time_utils import utc_now

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


@router.get("/status", response_model=TeamStatusResponse)
def get_team_status(
    group_id: Optional[int] = Query(None),
    status_filter: Optional[
        Literal["working", "on_break", "finished", "not_started"]
    ] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get the current account-scoped monitoring snapshot.
    - Admin: all active account users
    - Manager: active members of currently managed groups plus self
    - Employee: self only
    """
    service = TeamService(db)
    try:
        return service.get_monitoring_status(
            context,
            search=search,
            status_filter=status_filter,
            group_id=group_id,
            now=utc_now(),
        )
    except LookupError as error:
        raise not_found() from error


@router.get("/stats", response_model=TeamStats)
def get_team_stats(
    department: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Get team statistics"""
    service = TeamService(db)
    return service.get_team_stats(
        department,
        date_from,
        date_to,
        account_id=context.account_id,
        visible_external_user_ids=AccessPolicy(db, context).visible_external_user_ids(),
    )


@router.get("/activity", response_model=List[Dict[str, Any]])
def get_team_activity(
    date: datetime | None = Query(None),
    department: str | None = Query(None),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Get team activity for specific date"""
    service = TeamService(db)
    if not date:
        date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    return service.get_team_activity(
        date,
        department,
        account_id=context.account_id,
        visible_external_user_ids=AccessPolicy(db, context).visible_external_user_ids(),
    )


@router.get("/{target_user_id}/activity", response_model=ActivityWindowResponse)
def get_user_activity_window(
    target_user_id: int,
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Return up to seven inclusive local dates of safe activity detail."""
    try:
        return TeamService(db).get_activity_window(
            context, target_user_id, from_date, to_date
        )
    except LookupError as error:
        raise not_found() from error
    except ActivityRangeError as error:
        raise APIProblem(
            status.HTTP_400_BAD_REQUEST, error.code, error.message
        ) from error


@router.get("/{target_user_id}/timeline", response_model=ActivityTimelineResponse)
def get_user_timeline(
    target_user_id: int,
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get user CRM activity timeline for specific date.
    Timeline shows 15-minute intervals with activity counts.
    Only ROP/Admin can view.
    """
    policy = AccessPolicy(db, context)
    from app.models.user import User

    target_user = (
        db.query(User)
        .filter(
            User.amocrm_user_id == target_user_id,
            User.amocrm_account_id == context.account_id,
        )
        .first()
    )

    try:
        policy.require_view_user(target_user)
    except (LookupError, PermissionError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from error

    service = TeamService(db)
    return service.get_user_timeline(target_user_id, date, context.account_id)


@router.get(
    "/{target_user_id}/timeline/history", response_model=ActivityHistoryResponse
)
def get_user_timeline_history(
    target_user_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get user CRM activity history for last 7 days.
    Only ROP/Admin can view.
    """
    policy = AccessPolicy(db, context)
    from app.models.user import User

    target_user = (
        db.query(User)
        .filter(
            User.amocrm_user_id == target_user_id,
            User.amocrm_account_id == context.account_id,
        )
        .first()
    )

    try:
        policy.require_view_user(target_user)
    except (LookupError, PermissionError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from error

    service = TeamService(db)
    return service.get_user_timeline_history(target_user_id, context.account_id)


@router.post("/{target_user_id}/force-finish", response_model=ForceFinishResponse)
def force_finish_session(
    target_user_id: int,
    request: ForceFinishRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """
    Force finish work session for employee.
    Only Admin can force finish.
    """
    user = context.user

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not AccessPolicy(db, context).can_force_finish():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin can force finish sessions",
        )

    service = TeamService(db)
    return service.force_finish_session(
        target_user_id=target_user_id,
        admin_id=user.id,
        admin_name=user.name,
        reason=request.reason,
        account_id=context.account_id,
    )
