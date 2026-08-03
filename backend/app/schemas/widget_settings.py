from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any, List


class WidgetSettingsBase(BaseModel):
    """Base widget settings schema"""
    account_id: int
    account_name: Optional[str] = None
    polling_interval: int = Field(default=15, ge=5, le=60)
    inactivity_timeout: int = Field(default=300, ge=60, le=1800)
    enable_activity_tracking: bool = True
    enable_overlay_blocking: bool = True
    enable_auto_finish: bool = False
    excel_columns: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None


class WidgetSettingsCreate(WidgetSettingsBase):
    """Schema for creating widget settings"""
    pass


class WidgetSettingsUpdate(BaseModel):
    """Schema for updating widget settings"""
    account_name: Optional[str] = None
    polling_interval: Optional[int] = Field(default=None, ge=5, le=60)
    inactivity_timeout: Optional[int] = Field(default=None, ge=60, le=1800)
    enable_activity_tracking: Optional[bool] = None
    enable_overlay_blocking: Optional[bool] = None
    enable_auto_finish: Optional[bool] = None
    excel_columns: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None


class WidgetSettingsResponse(WidgetSettingsBase):
    """Schema for widget settings response"""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
