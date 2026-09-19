from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.group_member import GroupMember
from app.models.user import User, UserRole
from app.models.widget_group import WidgetGroup


class _ActorClient:
    def __init__(self, client: TestClient, user_id: int) -> None:
        self._client = client
        self._headers = {
            "X-User-Id": str(user_id),
            "X-Account-Id": "10",
        }

    def get(self, path: str, **kwargs):
        headers = {**self._headers, **kwargs.pop("headers", {})}
        return self._client.get(path, headers=headers, **kwargs)

    def put(self, path: str, **kwargs):
        headers = {**self._headers, **kwargs.pop("headers", {})}
        return self._client.put(path, headers=headers, **kwargs)

    def post(self, path: str, **kwargs):
        headers = {**self._headers, **kwargs.pop("headers", {})}
        return self._client.post(path, headers=headers, **kwargs)


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    database = sessionmaker(bind=engine)()
    database.add_all(
        [
            User(
                id=1,
                amocrm_user_id=101,
                amocrm_account_id=10,
                name="Admin",
                email="admin@example.test",
                amocrm_group_id=900,
                role=UserRole.ADMIN,
                amocrm_rights={"role_id": 70, "is_admin": True},
                amocrm_role_id=70,
            ),
            User(
                id=2,
                amocrm_user_id=102,
                amocrm_account_id=10,
                name="Employee",
                email="employee@example.test",
                amocrm_group_id=901,
                amocrm_rights={"role_id": 71, "is_admin": False},
                amocrm_role_id=71,
            ),
            User(
                id=3,
                amocrm_user_id=103,
                amocrm_account_id=10,
                name="Manager",
                email="manager@example.test",
                amocrm_group_id=None,
                role=UserRole.ROP,
                amocrm_rights={"role_id": 77, "is_admin": False},
                amocrm_role_id=77,
            ),
            User(
                id=4,
                amocrm_user_id=201,
                amocrm_account_id=11,
                name="Foreign admin",
                role=UserRole.ADMIN,
                amocrm_rights={"role_id": 80, "is_admin": True},
                amocrm_role_id=80,
            ),
            WidgetGroup(
                id=10,
                account_id=10,
                name="Zebra",
                timezone="Europe/Minsk",
                manager_user_id=3,
                manager_role_id=77,
            ),
            WidgetGroup(
                id=11,
                account_id=10,
                name="alpha",
                timezone="UTC",
                is_active=False,
                allow_restart_session=True,
            ),
            WidgetGroup(id=20, account_id=11, name="Foreign", timezone="UTC"),
            GroupMember(
                id=1,
                account_id=10,
                group_id=10,
                user_id=2,
                is_active=True,
                track_time=True,
                hide_widget=False,
            ),
        ]
    )
    database.commit()
    try:
        yield database
    finally:
        database.close()
        engine.dispose()


@pytest.fixture
def scoped_client(
    monkeypatch, db: Session
) -> Callable[[str], _ActorClient]:
    from app.main import app

    actor_ids = {"admin": 101, "employee": 102, "manager": 103}
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(app, "middleware_stack", None)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield lambda actor: _ActorClient(client, actor_ids[actor])
    app.dependency_overrides.clear()
