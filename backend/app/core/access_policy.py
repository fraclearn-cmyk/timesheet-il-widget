"""Account-scoped access rules for the widget's three roles."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.group_member import GroupMember
from app.models.user import User, UserRole
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
        if (
            self.context.privileges_verified
            and self.context.user.role == UserRole.ADMIN
        ):
            return True
        if (
            not self.context.privileges_verified
            or self.context.user.role != UserRole.ROP
        ):
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
