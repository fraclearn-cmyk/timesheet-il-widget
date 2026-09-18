from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.settings_service import SettingsService
from app.schemas.widget_settings import WidgetSettingsResponse, WidgetSettingsUpdate
from app.api.v1.dependencies import (
    APIProblem,
    RequestContext,
    get_request_context,
    require_account,
)

router = APIRouter()


@router.get("/{account_id}", response_model=WidgetSettingsResponse)
def get_settings(
    account_id: str,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Get widget settings for account"""
    require_account(context, account_id)
    service = SettingsService(db)
    settings = service.get_settings(account_id)

    if not settings:
        # Return defaults if not found
        return WidgetSettingsResponse(
            account_id=account_id,
            auto_pause_on_close=True,
            require_category=False,
            track_idle_time=False,
            idle_threshold_minutes=5,
            show_team_stats=True,
            enable_reports=True,
            config={},
        )

    return WidgetSettingsResponse.from_orm(settings)


@router.put("/{account_id}", response_model=WidgetSettingsResponse)
def update_settings(
    account_id: str,
    data: WidgetSettingsUpdate,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Create or update widget settings"""
    require_account(context, account_id)
    if context.user.role.value != "admin":
        raise APIProblem(403, "ACCESS_DENIED", "У вас нет доступа к этому разделу.")
    service = SettingsService(db)
    settings = service.create_or_update_settings(account_id, data)
    return WidgetSettingsResponse.from_orm(settings)


@router.post("/{account_id}/reset", response_model=WidgetSettingsResponse)
def reset_settings(
    account_id: str,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Reset settings to defaults"""
    require_account(context, account_id)
    if context.user.role.value != "admin":
        raise APIProblem(403, "ACCESS_DENIED", "У вас нет доступа к этому разделу.")
    service = SettingsService(db)
    settings = service.reset_settings(account_id)
    return WidgetSettingsResponse.from_orm(settings)
