from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.settings_service import SettingsService
from app.schemas.widget_settings import WidgetSettingsResponse, WidgetSettingsUpdate

router = APIRouter()


@router.get("/{account_id}", response_model=WidgetSettingsResponse)
def get_settings(
    account_id: str,
    db: Session = Depends(get_db)
):
    """Get widget settings for account"""
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
            config={}
        )
    
    return WidgetSettingsResponse.from_orm(settings)


@router.put("/{account_id}", response_model=WidgetSettingsResponse)
def update_settings(
    account_id: str,
    data: WidgetSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Create or update widget settings"""
    service = SettingsService(db)
    settings = service.create_or_update_settings(account_id, data)
    return WidgetSettingsResponse.from_orm(settings)


@router.post("/{account_id}/reset", response_model=WidgetSettingsResponse)
def reset_settings(
    account_id: str,
    db: Session = Depends(get_db)
):
    """Reset settings to defaults"""
    service = SettingsService(db)
    settings = service.reset_settings(account_id)
    return WidgetSettingsResponse.from_orm(settings)
