"""Account-scoped access rules for the widget's three roles."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.group_member import GroupMember
from app.models.user import User
from app.models.widget_group import WidgetGroup


@dataclass(frozen=True)
class RequestContext:
    account_id: int
    user: User
    privileges_verified: bool = True

    def __post_init__(self) -> None:
        if self.user.amocrm_account_id != self.account_id:
            raise ValueError("request context user belongs to another account")


class AccessPolicy:
    def __init__(self, db: Session, context: RequestContext) -> None:
        self._db, self.context = db, context

    def can_view_user(self, target: User) -> bool:
        if target.amocrm_account_id != self.context.account_id or not target.is_active:
            return False
        if target.id == self.context.user.id:
            return True
        if self.is_admin():
            return True
        if not self.is_manager():
            return False
        return (
            self._db.query(GroupMember.id)
            .join(
                WidgetGroup,
                (WidgetGroup.id == GroupMember.group_id)
                & (WidgetGroup.account_id == GroupMember.account_id),
            )
            .filter(
                GroupMember.account_id == self.context.account_id,
                GroupMember.user_id == target.id,
                GroupMember.is_active.is_(True),
                WidgetGroup.manager_user_id == self.context.user.id,
                WidgetGroup.is_active.is_(True),
            )
            .first()
            is not None
        )

    def is_admin(self) -> bool:
        rights = self.context.user.amocrm_rights
        return (
            self.context.privileges_verified
            and isinstance(rights, dict)
            and rights.get("is_admin") is True
        )

    def is_manager(self) -> bool:
        role_id = self.context.user.amocrm_role_id
        if not self.context.privileges_verified or not isinstance(role_id, int):
            return False
        return (
            self._db.query(WidgetGroup.id)
            .filter(
                WidgetGroup.account_id == self.context.account_id,
                WidgetGroup.manager_user_id == self.context.user.id,
                WidgetGroup.manager_role_id == role_id,
                WidgetGroup.is_active.is_(True),
            )
            .first()
            is not None
        )

    def can_view_department(self, department_id: int) -> bool:
        if self.is_admin():
            return (
                self._db.query(User.id)
                .filter(
                    User.amocrm_account_id == self.context.account_id,
                    User.department_id == department_id,
                    User.is_active.is_(True),
                )
                .first()
                is not None
            )
        if not self.is_manager():
            return False
        return (
            self._db.query(GroupMember.id)
            .join(User, User.id == GroupMember.user_id)
            .join(
                WidgetGroup,
                (WidgetGroup.id == GroupMember.group_id)
                & (WidgetGroup.account_id == GroupMember.account_id),
            )
            .filter(
                GroupMember.account_id == self.context.account_id,
                GroupMember.is_active.is_(True),
                User.department_id == department_id,
                User.is_active.is_(True),
                WidgetGroup.manager_user_id == self.context.user.id,
                WidgetGroup.manager_role_id == self.context.user.amocrm_role_id,
                WidgetGroup.is_active.is_(True),
            )
            .first()
            is not None
        )

    def accessible_department_ids(self) -> set[int] | None:
        if self.is_admin():
            return None
        if not self.is_manager():
            return set()
        rows = (
            self._db.query(User.department_id)
            .join(GroupMember, GroupMember.user_id == User.id)
            .join(
                WidgetGroup,
                (WidgetGroup.id == GroupMember.group_id)
                & (WidgetGroup.account_id == GroupMember.account_id),
            )
            .filter(
                User.amocrm_account_id == self.context.account_id,
                User.department_id.isnot(None),
                User.is_active.is_(True),
                GroupMember.account_id == self.context.account_id,
                GroupMember.is_active.is_(True),
                WidgetGroup.manager_user_id == self.context.user.id,
                WidgetGroup.manager_role_id == self.context.user.amocrm_role_id,
                WidgetGroup.is_active.is_(True),
            )
            .distinct()
            .all()
        )
        return {department_id for (department_id,) in rows}

    def can_force_finish(self) -> bool:
        return self.is_admin()

    def can_manage_departments(self) -> bool:
        return self.is_admin()

    def visible_users(self):
        return [
            user
            for user in self._db.query(User).filter(
                User.amocrm_account_id == self.context.account_id,
                User.is_active.is_(True),
            )
            if self.can_view_user(user)
        ]

    def visible_internal_user_ids(self) -> set[int]:
        """Return internal IDs allowed in response-set queries."""
        return {user.id for user in self.visible_users()}

    def visible_external_user_ids(self) -> set[int]:
        """Return amoCRM IDs allowed in response-set queries."""
        return {user.amocrm_user_id for user in self.visible_users()}

    def require_view_user(self, target: User | None) -> User:
        if target is None or target.amocrm_account_id != self.context.account_id:
            raise LookupError("not found")
        if not self.can_view_user(target):
            raise PermissionError("access denied")
        return target
