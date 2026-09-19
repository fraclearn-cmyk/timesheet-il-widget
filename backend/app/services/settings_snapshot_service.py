"""Read-only assembly of the canonical admin settings snapshot."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session

from app.api.v1.dependencies import access_denied
from app.core.access_policy import AccessPolicy, RequestContext
from app.models.group_member import GroupMember
from app.models.user import User
from app.models.widget_group import WidgetGroup
from app.models.widget_settings import WidgetSettings
from app.schemas.settings_snapshot import (
    AccountSettings,
    SettingsGroup,
    SettingsSnapshotResponse,
    SettingsUser,
)


DEFAULT_ALLOWED_STATUSES = ["working", "break", "finished"]
NO_AMOCRM_GROUP_LABEL = "Без группы amoCRM"


class SettingsSnapshotService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def load(self, context: RequestContext) -> SettingsSnapshotResponse:
        self._require_admin(context)
        settings = (
            self._db.query(WidgetSettings)
            .filter(WidgetSettings.account_id == context.account_id)
            .one_or_none()
        )
        account_settings = AccountSettings(
            support_phone=settings.support_phone if settings is not None else None,
            allowed_statuses=(
                list(settings.allowed_statuses)
                if settings is not None
                else list(DEFAULT_ALLOWED_STATUSES)
            ),
            default_allow_restart_session=(
                settings.default_allow_restart_session
                if settings is not None
                else False
            ),
        )
        return SettingsSnapshotResponse(
            revision=settings.revision if settings is not None else 1,
            settings=account_settings,
            groups=self._load_groups(context.account_id),
            users=self._load_users(context.account_id),
        )

    def _require_admin(self, context: RequestContext) -> None:
        if not AccessPolicy(self._db, context).is_admin():
            raise access_denied()

    def _load_groups(self, account_id: int) -> list[SettingsGroup]:
        rows = (
            self._db.query(WidgetGroup, User.amocrm_user_id)
            .outerjoin(
                User,
                and_(
                    User.id == WidgetGroup.manager_user_id,
                    User.amocrm_account_id == WidgetGroup.account_id,
                ),
            )
            .filter(WidgetGroup.account_id == account_id)
            .all()
        )
        rows.sort(key=lambda row: (row[0].name.casefold(), row[0].id))
        return [
            SettingsGroup(
                id=group.id,
                account_id=group.account_id,
                name=group.name,
                timezone=group.timezone,
                work_start_time=group.work_start_time,
                work_end_time=group.work_end_time,
                manager_amocrm_user_id=manager_amocrm_user_id,
                is_active=group.is_active,
                allow_restart_session=group.allow_restart_session,
            )
            for group, manager_amocrm_user_id in rows
        ]

    def _load_users(self, account_id: int) -> list[SettingsUser]:
        has_membership = exists().where(
            and_(
                GroupMember.account_id == account_id,
                GroupMember.user_id == User.id,
            )
        )
        users = (
            self._db.query(User)
            .filter(
                User.amocrm_account_id == account_id,
                or_(User.is_active.is_(True), has_membership),
            )
            .all()
        )
        users.sort(
            key=lambda user: (
                user.amocrm_group_id is None,
                user.amocrm_group_id or 0,
                user.name.casefold(),
                user.amocrm_user_id,
            )
        )
        memberships = (
            self._db.query(GroupMember)
            .filter(
                GroupMember.account_id == account_id,
                GroupMember.user_id.in_([user.id for user in users]),
            )
            .all()
            if users
            else []
        )
        selected_memberships: dict[int, GroupMember] = {}
        for membership in memberships:
            current = selected_memberships.get(membership.user_id)
            if current is None or self._membership_key(membership) > self._membership_key(
                current
            ):
                selected_memberships[membership.user_id] = membership

        result: list[SettingsUser] = []
        for user in users:
            membership = selected_memberships.get(user.id)
            result.append(
                SettingsUser(
                    amocrm_user_id=user.amocrm_user_id,
                    name=user.name,
                    email=user.email,
                    avatar_url=user.avatar_url,
                    amocrm_group_id=user.amocrm_group_id,
                    amocrm_group_label=self._amocrm_group_label(user.amocrm_group_id),
                    is_active=user.is_active,
                    track_time=membership.track_time if membership is not None else False,
                    hide_widget=membership.hide_widget if membership is not None else False,
                    group_id=membership.group_id if membership is not None else None,
                )
            )
        return result

    @staticmethod
    def _membership_key(membership: GroupMember) -> tuple[bool, datetime, int]:
        changed_at = membership.updated_at or membership.created_at or datetime.min
        return bool(membership.is_active), changed_at, membership.id or 0

    @staticmethod
    def _amocrm_group_label(amocrm_group_id: int | None) -> str:
        if amocrm_group_id is None:
            return NO_AMOCRM_GROUP_LABEL
        return f"Группа amoCRM #{amocrm_group_id}"
