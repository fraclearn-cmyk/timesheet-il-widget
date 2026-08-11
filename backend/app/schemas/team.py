"""Team schemas"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, List


class ForceFinishRequest(BaseModel):
    """Request to force finish work session"""
    reason: str


class ForceFinishResponse(BaseModel):
    """Response for force finish"""
    success: bool
    message: str
    session_id: int


class ActivityTimelineInterval(BaseModel):
    """Activity timeline interval (15 minutes)"""
    start_time: str  # "09:00"
    end_time: str    # "09:15"
    deals: int = 0
    contacts: int = 0
    companies: int = 0
    tasks: int = 0
    calls: int = 0
    total_events: int = 0


class ActivityTimelineResponse(BaseModel):
    """Activity timeline for a day"""
    user_id: int
    user_name: str
    date: str  # "2026-08-11"
    intervals: List[ActivityTimelineInterval]
    total_events: int
    
    
class ActivityHistoryDay(BaseModel):
    """Activity history for one day"""
    date: str
    total_events: int
    deals: int
    contacts: int
    companies: int
    tasks: int
    calls: int


class ActivityHistoryResponse(BaseModel):
    """Activity history for last 7 days"""
    user_id: int
    user_name: str
    days: List[ActivityHistoryDay]
