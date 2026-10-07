from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from app.core.database import get_db
from app.services.activity_service import ActivityService
from app.models.activity_session import EntityType
from app.models.activity_event import EventType
from app.schemas.activity_session import (
    ActivitySessionResponse,
    ActivitySessionWithEvents,
)
from app.schemas.activity_event import ActivityEventResponse
from app.api.v1.dependencies import (
    APIProblem,
    RequestContext,
    get_request_context,
    require_owned_activity_session,
    require_owned_work_session,
)
from app.core.access_policy import AccessPolicy
from app.core.config import settings
from app.core.time_utils import utc_now
from app.schemas.activity_ingestion import PresenceBatchCreate, PresenceIntervalResponse
from app.services.activity_interval_service import ActivityIntervalService
from app.services.webhook_subscription_service import (
    WebhookSubscriptionService,
    WebhookURLMissing,
)
from app.integrations.amocrm_client import AmoCRMClient
from app.integrations.http_transport import build_amocrm_async_transport
from app.integrations.oauth import OAuthTokenCipher
import httpx

router = APIRouter()


async def get_webhook_subscription_service(db: Session = Depends(get_db)):
    async with httpx.AsyncClient(
        transport=build_amocrm_async_transport(settings.AMOCRM_LOCAL_ADDRESS)
    ) as http_client:
        yield WebhookSubscriptionService(
            db,
            AmoCRMClient(http_client),
            OAuthTokenCipher.from_secret(settings.SECRET_KEY),
            public_base_url=settings.PUBLIC_BASE_URL,
            clock=utc_now,
        )


@router.post(
    "/presence",
    response_model=PresenceIntervalResponse,
    status_code=202,
    responses={204: {"description": "Presence recorded outside WORKING"}},
)
def record_presence(
    body: PresenceBatchCreate,
    response: Response,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    try:
        interval = ActivityIntervalService(db).record_presence(
            account_id=context.account_id,
            user=context.user,
            command_id=body.command_id,
            window_started_at=body.window_started_at.replace(tzinfo=None),
            last_seen_at=body.last_seen_at.replace(tzinfo=None),
            signal_count=body.signal_count,
            received_at=utc_now(),
        )
        db.commit()
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail="PRESENCE_BATCH_INVALID") from error
    if interval is None:
        return Response(status_code=204)
    response.status_code = 202
    return interval


@router.post("/ingestion/webhook/ensure")
async def ensure_ingestion_webhook(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
    service: WebhookSubscriptionService = Depends(get_webhook_subscription_service),
):
    if not AccessPolicy(db, context).is_admin():
        raise APIProblem(403, "ACCESS_DENIED", "У вас нет доступа к этому разделу.")
    if not settings.PUBLIC_BASE_URL:
        raise APIProblem(409, "WEBHOOK_URL_MISSING", "Публичный HTTPS URL не настроен.")
    try:
        await service.ensure(context.account_id)
    except WebhookURLMissing as error:
        raise APIProblem(
            409, "WEBHOOK_URL_MISSING", "Публичный HTTPS URL не настроен."
        ) from error
    return {"enabled": True}


@router.post("/start", response_model=ActivitySessionResponse, status_code=201)
def start_activity(
    work_session_id: int,
    entity_type: EntityType,
    entity_id: int,
    entity_name: Optional[str] = None,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Start new activity session (открыть карточку)"""
    require_owned_work_session(db, context, work_session_id)
    service = ActivityService(db)
    try:
        session = service.start_activity(
            work_session_id, entity_type, entity_id, entity_name
        )
        return ActivitySessionResponse.from_orm(session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/stop/{activity_session_id}", response_model=ActivitySessionResponse)
def stop_activity(
    activity_session_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Stop activity session (закрыть карточку)"""
    require_owned_activity_session(db, context, activity_session_id)
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
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Switch to another entity (переключиться на другую карточку)"""
    require_owned_work_session(db, context, work_session_id)
    service = ActivityService(db)
    try:
        session = service.switch_activity(
            work_session_id, entity_type, entity_id, entity_name
        )
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
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Track event in activity session (зафиксировать событие)"""
    require_owned_activity_session(db, context, activity_session_id)
    service = ActivityService(db)
    try:
        event = service.track_event(
            activity_session_id, event_type, event_data, description, category_id
        )
        return ActivityEventResponse.from_orm(event)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/current/{work_session_id}", response_model=Optional[ActivitySessionWithEvents]
)
def get_current_activity(work_session_id: int, db: Session = Depends(get_db)):
    """Get current active activity session"""
    service = ActivityService(db)
    session = service.get_current_activity(work_session_id)

    if not session:
        return None

    return ActivitySessionWithEvents.from_orm(session)


@router.get("/history/{work_session_id}", response_model=List[ActivitySessionResponse])
def get_activity_history(
    work_session_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get activity history for work session"""
    service = ActivityService(db)
    sessions = service.get_activity_history(work_session_id, limit)
    return [ActivitySessionResponse.from_orm(s) for s in sessions]


@router.get("/events/{activity_session_id}", response_model=List[ActivityEventResponse])
def get_activity_events(activity_session_id: int, db: Session = Depends(get_db)):
    """Get all events for activity session"""
    service = ActivityService(db)
    events = service.get_events(activity_session_id)
    return [ActivityEventResponse.from_orm(e) for e in events]


@router.get("/stats/{work_session_id}", response_model=Dict[str, Any])
def get_activity_stats(work_session_id: int, db: Session = Depends(get_db)):
    """Get activity statistics for work session"""
    service = ActivityService(db)
    return service.get_activity_stats(work_session_id)
