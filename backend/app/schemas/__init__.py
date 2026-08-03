"""Pydantic schemas for request/response validation"""
from app.schemas.work_session import (
    WorkSessionCreate,
    WorkSessionUpdate,
    WorkSessionResponse,
    WorkSessionWithDetails,
)
from app.schemas.status_transition import (
    StatusTransitionCreate,
    StatusTransitionResponse,
)
from app.schemas.activity_session import (
    ActivitySessionCreate,
    ActivitySessionUpdate,
    ActivitySessionResponse,
    ActivitySessionWithEvents,
)
from app.schemas.activity_event import (
    ActivityEventCreate,
    ActivityEventResponse,
)
from app.schemas.activity_category import (
    ActivityCategoryCreate,
    ActivityCategoryUpdate,
    ActivityCategoryResponse,
)
from app.schemas.widget_settings import (
    WidgetSettingsCreate,
    WidgetSettingsUpdate,
    WidgetSettingsResponse,
)

__all__ = [
    # Work Session
    "WorkSessionCreate",
    "WorkSessionUpdate",
    "WorkSessionResponse",
    "WorkSessionWithDetails",
    # Status Transition
    "StatusTransitionCreate",
    "StatusTransitionResponse",
    # Activity Session
    "ActivitySessionCreate",
    "ActivitySessionUpdate",
    "ActivitySessionResponse",
    "ActivitySessionWithEvents",
    # Activity Event
    "ActivityEventCreate",
    "ActivityEventResponse",
    # Activity Category
    "ActivityCategoryCreate",
    "ActivityCategoryUpdate",
    "ActivityCategoryResponse",
    # Widget Settings
    "WidgetSettingsCreate",
    "WidgetSettingsUpdate",
    "WidgetSettingsResponse",
]
