"""Team schemas"""

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Dict, List, Literal


class _StrictTeamModel(BaseModel):
    """Strict phase-6 public DTO base."""

    model_config = ConfigDict(extra="forbid")


class TeamViewer(_StrictTeamModel):
    id: int
    role: Literal["admin", "manager", "employee"]
    can_view_activity: bool


class TeamGroupSummary(_StrictTeamModel):
    id: int
    name: str
    timezone: str
    workday_started_at: datetime
    workday_ended_at: datetime
    employee_count: int


class TeamMemberSummary(_StrictTeamModel):
    id: int
    amocrm_user_id: int
    account_id: int
    name: str
    avatar_url: str | None
    group_id: int | None
    group_name: str | None
    timezone: str
    workday_started_at: datetime
    workday_ended_at: datetime
    status: Literal["working", "on_break", "finished", "not_started"]
    status_since: datetime | None
    session_started_at: datetime | None
    session_ended_at: datetime | None
    work_seconds: int
    break_seconds: int
    confirmed_seconds: int
    confirmed_events: int
    activity_detail_allowed: bool


class TeamStatusTotals(_StrictTeamModel):
    employees: int
    working: int
    on_break: int
    finished: int
    not_started: int
    work_seconds: int
    break_seconds: int
    confirmed_seconds: int
    confirmed_events: int


class TeamStatusResponse(_StrictTeamModel):
    generated_at: datetime
    viewer: TeamViewer
    groups: list[TeamGroupSummary]
    employees: list[TeamMemberSummary]
    totals: TeamStatusTotals


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
    end_time: str  # "09:15"
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
