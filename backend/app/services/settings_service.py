from sqlalchemy.orm import Session
from typing import Optional
from app.models.widget_settings import WidgetSettings
from app.schemas.widget_settings import WidgetSettingsCreate, WidgetSettingsUpdate


class SettingsService:
    """Service for managing widget settings"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_settings(self, account_id: str) -> Optional[WidgetSettings]:
        """Get settings for account"""
        return self.db.query(WidgetSettings)\
            .filter(WidgetSettings.account_id == account_id)\
            .first()
    
    def create_or_update_settings(
        self, 
        account_id: str, 
        data: WidgetSettingsUpdate
    ) -> WidgetSettings:
        """Create or update settings"""
        settings = self.get_settings(account_id)
        
        if not settings:
            # Create new
            settings = WidgetSettings(
                account_id=account_id,
                auto_pause_on_close=data.auto_pause_on_close,
                require_category=data.require_category,
                track_idle_time=data.track_idle_time,
                idle_threshold_minutes=data.idle_threshold_minutes,
                show_team_stats=data.show_team_stats,
                enable_reports=data.enable_reports,
                config=data.config
            )
            self.db.add(settings)
        else:
            # Update existing
            if data.auto_pause_on_close is not None:
                settings.auto_pause_on_close = data.auto_pause_on_close
            if data.require_category is not None:
                settings.require_category = data.require_category
            if data.track_idle_time is not None:
                settings.track_idle_time = data.track_idle_time
            if data.idle_threshold_minutes is not None:
                settings.idle_threshold_minutes = data.idle_threshold_minutes
            if data.show_team_stats is not None:
                settings.show_team_stats = data.show_team_stats
            if data.enable_reports is not None:
                settings.enable_reports = data.enable_reports
            if data.config is not None:
                settings.config = data.config
        
        self.db.commit()
        self.db.refresh(settings)
        return settings
    
    def reset_settings(self, account_id: str) -> WidgetSettings:
        """Reset settings to defaults"""
        settings = self.get_settings(account_id)
        
        if not settings:
            settings = WidgetSettings(account_id=account_id)
            self.db.add(settings)
        else:
            settings.auto_pause_on_close = True
            settings.require_category = False
            settings.track_idle_time = False
            settings.idle_threshold_minutes = 5
            settings.show_team_stats = True
            settings.enable_reports = True
            settings.config = {}
        
        self.db.commit()
        self.db.refresh(settings)
        return settings
