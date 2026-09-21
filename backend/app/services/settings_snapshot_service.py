"""Canonical settings snapshot with validated, atomic account-scoped saves."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

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
    SettingsSnapshotUpdate,
    SettingsUser,
)


DEFAULT_ALLOWED_STATUSES = ["working", "break", "finished"]
NO_AMOCRM_GROUP_LABEL = "Без группы amoCRM"


class SettingsProblem(Exception):
    def __init__(
        self, code: str, message: str, field: str | None = None, status: int = 409
    ):
        self.status = status
        self.error = {"code": code, "message": message}
        if field is not None:
            self.error["field"] = field
        super().__init__(code)


class SettingsSnapshotService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def save(
        self, context: RequestContext, payload: SettingsSnapshotUpdate
    ) -> SettingsSnapshotResponse:
        self._require_admin(context)
        try:
            with self._db.no_autoflush:
                # An account always has a verified user. Lock its first user to
                # serialize even the first save, when no settings row exists.
                self._db.query(User.id).filter(
                    User.amocrm_account_id == context.account_id
                ).order_by(User.id).limit(1).with_for_update().one()
                current = (
                    self._db.query(WidgetSettings)
                    .filter_by(account_id=context.account_id)
                    .populate_existing()
                    .with_for_update()
                    .one_or_none()
                )
                revision = current.revision if current is not None else 1
                if payload.revision != revision:
                    raise SettingsProblem(
                        "SETTINGS_VERSION_CONFLICT",
                        "Настройки уже изменены другим администратором.",
                    )
                groups, users, memberships, selected = self._validate_snapshot(
                    context.account_id, payload
                )

            if current is None:
                current = WidgetSettings(
                    account_id=context.account_id, revision=revision
                )
                self._db.add(current)
            for key, value in payload.settings.model_dump().items():
                setattr(current, key, value)
            group_ids = self._upsert_groups(context.account_id, payload, groups, users)
            self._replace_memberships(
                context.account_id, payload, users, memberships, selected, group_ids
            )
            current.revision = revision + 1
            self._db.flush()
            # Assemble before commit: a failure reading/validating the response
            # must also roll back all writes.
            result = self.load(context)
            self._db.commit()
            return result
        except SQLAlchemyError as error:
            self._db.rollback()
            raise SettingsProblem(
                "SETTINGS_SAVE_CONFLICT",
                "Не удалось сохранить настройки. Обновите данные и повторите попытку.",
            ) from error
        except Exception:
            self._db.rollback()
            raise

    def _validate_snapshot(self, account_id: int, payload: SettingsSnapshotUpdate):
        groups = {
            g.id: g
            for g in self._db.query(WidgetGroup).filter_by(account_id=account_id)
        }
        users = {
            u.amocrm_user_id: u
            for u in self._db.query(User).filter_by(amocrm_account_id=account_id)
        }
        memberships = self._db.query(GroupMember).filter_by(account_id=account_id).all()
        selected = {}
        for member in memberships:
            previous = selected.get(member.user_id)
            if previous is None or self._membership_key(member) > self._membership_key(
                previous
            ):
                selected[member.user_id] = member

        if len(set(payload.settings.allowed_statuses)) != len(
            payload.settings.allowed_statuses
        ):
            raise SettingsProblem(
                "SETTINGS_INVALID",
                "Рабочие статусы не должны повторяться.",
                "settings.allowed_statuses",
            )
        references = {}
        names = {}
        for index, group in enumerate(payload.groups):
            field = f"groups.{index}"
            if (group.id is None) == (group.client_key is None):
                raise SettingsProblem(
                    "GROUP_REFERENCE_INVALID",
                    "Укажите ID группы или временный ключ.",
                    f"{field}.id",
                )
            reference_field = "id" if group.id is not None else "client_key"
            if group.reference in references:
                raise SettingsProblem(
                    "GROUP_REFERENCE_DUPLICATE",
                    "Группа указана несколько раз.",
                    f"{field}.{reference_field}",
                )
            if group.id is not None and group.id not in groups:
                raise SettingsProblem(
                    "GROUP_NOT_FOUND",
                    "Группа не найдена в текущем аккаунте.",
                    f"{field}.id",
                    404,
                )
            references[group.reference] = group
            group.name = group.name.strip()
            if not group.name:
                raise SettingsProblem(
                    "GROUP_NAME_REQUIRED", "Укажите название группы.", f"{field}.name"
                )
            name_key = group.name.casefold()
            if name_key in names:
                raise SettingsProblem(
                    "GROUP_DUPLICATE",
                    "Группа с таким названием уже существует.",
                    f"{field}.name",
                )
            names[name_key] = index
            try:
                ZoneInfo(group.timezone)
            except (ZoneInfoNotFoundError, ValueError):
                raise SettingsProblem(
                    "GROUP_TIMEZONE_INVALID",
                    "Выберите действительный часовой пояс IANA.",
                    f"{field}.timezone",
                ) from None
            if (
                group.work_start_time == group.work_end_time
                or group.work_start_time.tzinfo is not None
                or group.work_end_time.tzinfo is not None
            ):
                raise SettingsProblem(
                    "GROUP_SCHEDULE_INVALID",
                    "Укажите различное время начала и конца рабочего дня без часового пояса.",
                    f"{field}.work_end_time",
                )
            if group.manager_amocrm_user_id is not None:
                manager = users.get(group.manager_amocrm_user_id)
                if (
                    manager is None
                    or not manager.is_active
                    or manager.amocrm_role_id is None
                ):
                    raise SettingsProblem(
                        "GROUP_MANAGER_INVALID",
                        "Выберите активного руководителя текущего аккаунта с известной ролью amoCRM.",
                        f"{field}.manager_amocrm_user_id",
                    )

        # Omitted groups remain historical rows, so their names remain reserved.
        for group_id, group in groups.items():
            if f"id:{group_id}" not in references and group.name_key in names:
                index = names[group.name_key]
                raise SettingsProblem(
                    "GROUP_DUPLICATE",
                    "Группа с таким названием уже существует.",
                    f"groups.{index}.name",
                )

        seen_users = set()
        for index, entry in enumerate(payload.users):
            field = f"users.{index}"
            if entry.amocrm_user_id in seen_users:
                raise SettingsProblem(
                    "USER_DUPLICATE",
                    "Сотрудник указан несколько раз.",
                    f"{field}.amocrm_user_id",
                )
            seen_users.add(entry.amocrm_user_id)
            user = users.get(entry.amocrm_user_id)
            if user is None:
                raise SettingsProblem(
                    "USER_NOT_FOUND",
                    "Сотрудник не найден в текущем аккаунте.",
                    f"{field}.amocrm_user_id",
                    404,
                )
            previous = selected.get(user.id)
            previous_ref = f"id:{previous.group_id}" if previous is not None else None
            if not user.is_active:
                if (
                    previous is None
                    or entry.group_ref != previous_ref
                    or entry.track_time != previous.track_time
                    or entry.hide_widget != user.hide_widget
                ):
                    raise SettingsProblem(
                        "USER_INACTIVE",
                        "Нельзя изменять настройки неактивного сотрудника.",
                        f"{field}.amocrm_user_id",
                    )
                group = references.get(previous_ref)
                if previous.is_active and (group is None or not group.is_active):
                    raise SettingsProblem(
                        "GROUP_IN_USE",
                        "Нельзя отключить группу с активным членством неактивного сотрудника.",
                        "groups",
                    )
                continue
            if entry.track_time and entry.group_ref is None:
                raise SettingsProblem(
                    "TRACKED_USER_GROUP_REQUIRED",
                    "Для учёта сотруднику нужно назначить группу.",
                    f"{field}.group_ref",
                )
            if entry.group_ref is not None:
                group = references.get(entry.group_ref)
                # An unchanged historical reference remains displayable after
                # disabling tracking or deactivating/omitting its group.
                historical = not entry.track_time and entry.group_ref == previous_ref
                if group is None and not historical:
                    raise SettingsProblem(
                        "GROUP_NOT_FOUND",
                        "Группа не найдена в текущем снимке.",
                        f"{field}.group_ref",
                        404,
                    )
                if group is not None and not group.is_active and not historical:
                    raise SettingsProblem(
                        "GROUP_INACTIVE",
                        "Выберите активную группу учёта.",
                        f"{field}.group_ref",
                    )
        # This is a full snapshot, not a patch. Match the reader's visible set
        # (active users plus users with history), so omissions cannot silently
        # disable inactive users or retain tracked history without participation.
        required_users = {
            user.amocrm_user_id
            for user in users.values()
            if user.is_active or user.id in selected
        }
        if required_users - seen_users:
            raise SettingsProblem(
                "SETTINGS_USERS_INCOMPLETE",
                "Снимок должен содержать всех пользователей. Обновите данные и повторите попытку.",
                "users",
            )
        return groups, users, memberships, selected

    def _upsert_groups(self, account_id, payload, existing, users):
        # Release only renamed keys before writing the final set, allowing name
        # swaps under the non-deferrable unique constraint in either database.
        for entry in payload.groups:
            if (
                entry.id is not None
                and existing[entry.id].name_key != entry.name.casefold()
            ):
                existing[entry.id].name_key = f"__snapshot_{uuid4().hex}"
        self._db.flush()
        result = {}
        for entry in payload.groups:
            group = existing.get(entry.id)
            if group is None:
                group = WidgetGroup(account_id=account_id)
                self._db.add(group)
            for key in (
                "name",
                "timezone",
                "work_start_time",
                "work_end_time",
                "is_active",
                "allow_restart_session",
            ):
                setattr(group, key, getattr(entry, key))
            if entry.manager_amocrm_user_id is None:
                group.manager_user_id = group.manager_role_id = None
            else:
                group.assign_manager(users[entry.manager_amocrm_user_id])
            result[entry.reference] = group
        included = {entry.id for entry in payload.groups if entry.id is not None}
        for group_id, group in existing.items():
            if group_id not in included:
                group.is_active = False
        self._db.flush()
        return {reference: group.id for reference, group in result.items()}

    def _replace_memberships(
        self, account_id, payload, users, memberships, selected, group_ids
    ):
        entries = {users[entry.amocrm_user_id].id: entry for entry in payload.users}
        active_user_ids = {user.id for user in users.values() if user.is_active}
        for member in memberships:
            if not member.is_active or member.user_id not in active_user_ids:
                continue
            entry = entries[member.user_id]
            if (
                not entry.track_time
                or group_ids.get(entry.group_ref) != member.group_id
            ):
                member.is_active = False
                if not entry.track_time:
                    member.track_time = False
        # Close the old active row before inserting its replacement so the
        # partial unique index never observes two active rows for one user.
        self._db.flush()
        for entry in payload.users:
            user = users[entry.amocrm_user_id]
            if not user.is_active:
                continue
            user.hide_widget = entry.hide_widget
            previous = selected.get(user.id)
            group_id = group_ids.get(entry.group_ref)
            if group_id is None:
                if previous is not None and not entry.track_time:
                    previous.track_time = False
                continue
            active = entry.track_time
            if (
                previous is not None
                and previous.group_id == group_id
                and previous.is_active == active
            ):
                previous.track_time = entry.track_time
                # Historical rows retain their last visibility snapshot.
                if active:
                    previous.hide_widget = entry.hide_widget
            else:
                self._db.add(
                    GroupMember(
                        account_id=account_id,
                        group_id=group_id,
                        user_id=user.id,
                        is_active=active,
                        track_time=entry.track_time,
                        hide_widget=entry.hide_widget,
                    )
                )

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
            if current is None or self._membership_key(
                membership
            ) > self._membership_key(current):
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
                    track_time=(
                        membership.track_time if membership is not None else False
                    ),
                    hide_widget=user.hide_widget,
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
