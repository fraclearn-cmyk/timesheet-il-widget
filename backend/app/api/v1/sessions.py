from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from app.core.database import get_db
from app.services.session_service import SessionService
from app.schemas.work_session import (
    WorkSessionCreate,
    WorkSessionResponse,
    WorkSessionWithDetails,
)
from app.api.v1.dependencies import (
    APIProblem,
    RequestContext,
    get_request_context,
    require_self_external_user,
    require_visible_external_user,
    require_visible_work_session,
)

router = APIRouter()


@router.post("/start", response_model=WorkSessionResponse, status_code=201)
def start_session(
    data: WorkSessionCreate,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Start new work session"""
    service = SessionService(db)
    try:
        if isinstance(context, RequestContext):
            require_self_external_user(context, data.user_id)
        session = service.start_session(data)
        return WorkSessionResponse.model_validate(session)
    except ValueError as e:
        raise APIProblem(
            409, "SESSION_CONFLICT", "Состояние рабочей сессии изменилось."
        ) from e


@router.post("/break/{user_id}", response_model=WorkSessionResponse)
def take_break(
    user_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Take a break"""
    service = SessionService(db)
    try:
        if isinstance(context, RequestContext):
            require_self_external_user(context, user_id)
        session = service.take_break(user_id)
        return WorkSessionResponse.model_validate(session)
    except ValueError as e:
        raise APIProblem(
            409, "SESSION_CONFLICT", "Состояние рабочей сессии изменилось."
        ) from e


@router.post("/resume/{user_id}", response_model=WorkSessionResponse)
def resume_work(
    user_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Resume work from break"""
    service = SessionService(db)
    try:
        if isinstance(context, RequestContext):
            require_self_external_user(context, user_id)
        session = service.resume_work(user_id)
        return WorkSessionResponse.model_validate(session)
    except ValueError as e:
        raise APIProblem(
            409, "SESSION_CONFLICT", "Состояние рабочей сессии изменилось."
        ) from e


@router.post("/finish/{user_id}", response_model=WorkSessionResponse)
def finish_session(
    user_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Finish work session"""
    service = SessionService(db)
    try:
        if isinstance(context, RequestContext):
            require_self_external_user(context, user_id)
        session = service.finish_work(user_id)
        return WorkSessionResponse.model_validate(session)
    except ValueError as e:
        raise APIProblem(
            409, "SESSION_CONFLICT", "Состояние рабочей сессии изменилось."
        ) from e


@router.get("/current/{user_id}", response_model=Optional[WorkSessionWithDetails])
def get_current_session(
    user_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Get user's current active session"""
    require_visible_external_user(db, context, user_id)
    service = SessionService(db)
    session = service.get_current_session(context.account_id, user_id)

    if not session:
        return None

    return WorkSessionWithDetails.model_validate(session)


@router.get("/history/{user_id}", response_model=List[WorkSessionResponse])
def get_session_history(
    user_id: int,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Get user's session history"""
    require_visible_external_user(db, context, user_id)
    service = SessionService(db)
    sessions = service.get_session_history(
        user_id, date_from, date_to, limit, account_id=context.account_id
    )
    return [WorkSessionResponse.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=WorkSessionWithDetails)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Get session by ID with details"""
    session = require_visible_work_session(db, context, session_id)

    return WorkSessionWithDetails.model_validate(session)
