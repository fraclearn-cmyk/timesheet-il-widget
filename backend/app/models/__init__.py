"""Database models"""
from app.models.user import User, UserRole
from app.models.department import Department
from app.models.rop_permission import RopPermission
from app.models.work_session import WorkSession, WorkStatus
from app.models.status_transition import StatusTransition
from app.models.activity_session import ActivitySession
from app.models.activity_event import ActivityEvent
from app.models.activity_category import ActivityCategory
from app.models.widget_settings import WidgetSettings
from app.models.report import Report
from app.models.work_comment import WorkComment
from app.models.dashboard_settings import DashboardSettings
from app.models.widget_group import WidgetGroup
from app.models.group_member import GroupMember
from app.models.crm_event import CrmEvent
from app.models.call_event import CallEvent
from app.models.activity_interval import ActivityInterval
from app.models.oauth_connection import OAuthConnection

__all__ = [
    "User",
    "UserRole",
    "Department",
    "RopPermission",
    "WorkSession",
    "WorkStatus",
    "StatusTransition",
    "ActivitySession",
    "ActivityEvent",
    "ActivityCategory",
    "WidgetSettings",
    "Report",
    "WorkComment",
    "DashboardSettings",
    "WidgetGroup",
    "GroupMember",
    "CrmEvent",
    "CallEvent",
    "ActivityInterval",
    "OAuthConnection",
]
