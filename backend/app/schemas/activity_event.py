from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any
from app.models.activity_event import EventType


class ActivityEventBase(BaseModel):
    """Base activity event schema"""
    event_type: EventType
    event_data: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    category_id: Optional[int] = None


class ActivityEventCreate(ActivityEventBase):
    """Schema for creating activity event"""
    activity_session_id: int


class ActivityEventResponse(ActivityEventBase):
    """Schema for activity event response"""
    id: int
    activity_session_id: int
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True
