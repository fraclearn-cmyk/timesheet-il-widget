from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from app.models.work_session import WorkStatus


class WorkSessionBase(BaseModel):
    """Base work session schema"""
    user_id: int
    user_name: str
    department: Optional[str] = None


class WorkSessionCreate(WorkSessionBase):
    """Schema for creating work session"""
    pass


class WorkSessionUpdate(BaseModel):
    """Schema for updating work session"""
    current_status: Optional[WorkStatus] = None
    end_time: Optional[datetime] = None
    total_work_time: Optional[int] = None
    total_break_time: Optional[int] = None
    break_count: Optional[int] = None


class WorkSessionResponse(WorkSessionBase):
    """Schema for work session response"""
    id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    current_status: WorkStatus
    total_work_time: int = 0
    total_break_time: int = 0
    break_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkSessionWithDetails(WorkSessionResponse):
    """Work session with related data"""
    status_transitions: List[StatusTransitionResponse] = []
    activity_sessions: List[ActivitySessionResponse] = []

    class Config:
        from_attributes = True


# Resolve forward references after all models are defined
from app.schemas.status_transition import StatusTransitionResponse
from app.schemas.activity_session import ActivitySessionResponse

WorkSessionWithDetails.model_rebuild()
