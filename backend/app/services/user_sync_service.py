"""Non-destructive synchronization of amoCRM users into the phase-1 identity model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from sqlalchemy.orm import Session

from app.models.oauth_connection import OAuthConnection
from app.models.user import User


class AmoCRMUserReader(Protocol):
    async def get_account(self) -> Mapping[str, Any]:
        raise NotImplementedError

    async def list_users(self) -> list[Mapping[str, Any]]:
        raise NotImplementedError


@dataclass(frozen=True)
class SyncResult:
    account_id: int
    created: int
    updated: int
    deactivated: int


class UserSyncService:
    def __init__(self, db: Session, client: AmoCRMUserReader) -> None:
        self._db, self._client = db, client

    async def synchronize(self) -> SyncResult:
        account = await self._client.get_account()
        account_id = account.get("id") if isinstance(account, Mapping) else None
        if (
            not isinstance(account_id, int)
            or isinstance(account_id, bool)
            or account_id <= 0
        ):
            raise ValueError("amoCRM account payload lacks a valid ID")
        users = await self._client.list_users()
        seen: set[int] = set()
        created = updated = 0
        for payload in users:
            external_id, name = payload.get("id"), payload.get("name")
            if (
                not isinstance(external_id, int)
                or isinstance(external_id, bool)
                or external_id <= 0
                or not isinstance(name, str)
                or not name.strip()
            ):
                continue
            seen.add(external_id)
            user = (
                self._db.query(User)
                .filter(
                    User.amocrm_account_id == account_id,
                    User.amocrm_user_id == external_id,
                )
                .one_or_none()
            )
            if user is None:
                user = User(
                    amocrm_account_id=account_id,
                    amocrm_user_id=external_id,
                    name=name.strip(),
                )
                self._db.add(user)
                created += 1
            else:
                updated += 1
                user.name = name.strip()
            user.email = (
                payload.get("email") if isinstance(payload.get("email"), str) else None
            )
            user.avatar_url = (
                payload.get("avatar")
                if isinstance(payload.get("avatar"), str)
                else None
            )
            rights = payload.get("rights")
            user.amocrm_rights = dict(rights) if isinstance(rights, Mapping) else None
            role_id = rights.get("role_id") if isinstance(rights, Mapping) else None
            user.amocrm_role_id = (
                role_id
                if isinstance(role_id, int) and not isinstance(role_id, bool)
                else None
            )
            user.is_active = (
                not bool(payload.get("is_deleted", False))
                and payload.get("is_active", True) is not False
            )
        existing = (
            self._db.query(User).filter(User.amocrm_account_id == account_id).all()
        )
        deactivated = 0
        for user in existing:
            if user.amocrm_user_id not in seen and user.is_active:
                user.is_active = False
                deactivated += 1
        connection = self._db.get(OAuthConnection, account_id)
        if connection is not None:
            connection.account_name = (
                account.get("name") if isinstance(account.get("name"), str) else None
            )
        self._db.commit()
        return SyncResult(account_id, created, updated, deactivated)
