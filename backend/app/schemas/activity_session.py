from __future__ import annotations

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.models.activity_session import EntityType


class ActivitySessionBase(BaseModel):
    """Base activity session schema"""
    entity_type: EntityType
    entity_id: int
    entity_name: Optional[str] = None


class ActivitySessionCreate(ActivitySessionBase):
    """Schema for creating activity session"""
    work_session_id: int


class ActivitySessionUpdate(BaseModel):
    """Schema for updating activity session"""
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    is_active: Optional[int] = None
    last_activity_time: Optional[datetime] = None


class ActivitySessionResponse(ActivitySessionBase):
    """Schema for activity session response"""
    id: int
    work_session_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    is_active: int
    last_activity_time: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ActivitySessionWithEvents(ActivitySessionResponse):
    """Activity session with events"""
    activity_events: List[ActivityEventResponse] = []

    class Config:
        from_attributes = True


# Resolve forward references after all models are defined
from app.schemas.activity_event import ActivityEventResponse

ActivitySessionWithEvents.model_rebuild()
