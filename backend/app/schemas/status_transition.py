from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class StatusTransitionBase(BaseModel):
    """Base status transition schema"""
    from_status: Optional[str] = None
    to_status: str
    reason: Optional[str] = None
    notes: Optional[str] = None


class StatusTransitionCreate(StatusTransitionBase):
    """Schema for creating status transition"""
    work_session_id: int


class StatusTransitionResponse(StatusTransitionBase):
    """Schema for status transition response"""
    id: int
    work_session_id: int
    timestamp: datetime
    duration: Optional[int] = None

    class Config:
        from_attributes = True
