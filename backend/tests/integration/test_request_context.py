import pytest
import asyncio
from starlette.requests import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.dependencies import (
    RequestContextUnauthorized,
    resolve_legacy_test_context,
)
from app.core.database import Base
from app.models.user import User
from app.models.user import UserRole
from app.models.oauth_connection import OAuthConnection
from app.integrations.oauth import OAuthTokenCipher


def test_legacy_identity_headers_fail_closed_outside_test_environment(monkeypatch):
    """Accepting forged X-User-Id/X-Account-Id in production must fail."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, amocrm_user_id=10, amocrm_account_id=20, name="User"))
    db.commit()
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RequestContextUnauthorized):
        resolve_legacy_test_context(db, "10", "20")


def test_legacy_identity_headers_resolve_only_the_matching_active_test_user(
    monkeypatch,
):
    """Dropping account or active predicates would authenticate the wrong principal."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            User(id=1, amocrm_user_id=10, amocrm_account_id=20, name="Active"),
            User(id=2, amocrm_user_id=10, amocrm_account_id=21, name="Other account"),
        ]
    )
    db.commit()
    monkeypatch.setenv("ENVIRONMENT", "test")

    context = resolve_legacy_test_context(db, "10", "20")

    assert context.account_id == 20
    assert context.user.id == 1


def test_me_requires_context_and_ignores_forged_query_identity(monkeypatch):
    """A missing context or a browser-supplied account must not select the principal."""
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, amocrm_user_id=10, amocrm_account_id=20, name="Active"))
    db.commit()
    monkeypatch.setenv("ENVIRONMENT", "test")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    try:
        assert client.get("/api/v1/me").status_code == 401
        response = client.get(
            "/api/v1/me?account_id=999&user_id=999",
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 200
        assert response.json()["account_id"] == 20
        assert response.json()["user"]["amocrm_id"] == 10
    finally:
        app.dependency_overrides.clear()


def _production_context_db(role):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(
        id=1,
        amocrm_user_id=10,
        amocrm_account_id=20,
        name="Current",
        role=role,
    )
    cipher = OAuthTokenCipher.from_secret(
        "synthetic-test-key-with-at-least-32-characters"
    )
    db.add_all(
        [
            user,
            OAuthConnection(
                account_id=20,
                account_url="https://example.amocrm.ru",
                encrypted_access_token=cipher.encrypt("access-token"),
                encrypted_refresh_token=cipher.encrypt("refresh-token"),
            ),
        ]
    )
    db.commit()
    return db


def _production_request():
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/me",
            "headers": [(b"authorization", b"Bearer access-token")],
        }
    )


def test_production_context_uses_observed_rights_without_inventing_is_active(
    monkeypatch,
):
    """The observed contract has role_id/is_admin; is_active is not required."""
    from app.api.v1 import dependencies

    class FakeClient:
        async def get_account(self, account_url, access_token):
            return {"id": 20, "current_user_id": 10}

        async def list_users(self, account_url, access_token):
            return [{"id": 10, "rights": {"role_id": 77, "is_admin": False}}]

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(dependencies, "AmoCRMClient", lambda http: FakeClient())
    db = _production_context_db(UserRole.ROP)

    context = asyncio.run(dependencies.get_request_context(_production_request(), db))

    assert context.user.role is UserRole.ROP
    assert context.user.amocrm_role_id == 77
    assert context.privileges_verified is True


def test_production_admin_downgrade_fails_closed(monkeypatch):
    """An admin's live amoCRM grant must remain is_admin=true."""
    from app.api.v1 import dependencies

    class FakeClient:
        async def get_account(self, account_url, access_token):
            return {"id": 20, "current_user_id": 10}

        async def list_users(self, account_url, access_token):
            return [{"id": 10, "rights": {"role_id": 77, "is_admin": False}}]

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(dependencies, "AmoCRMClient", lambda http: FakeClient())
    db = _production_context_db(UserRole.ADMIN)
    with pytest.raises(dependencies.APIProblem) as error:
        asyncio.run(dependencies.get_request_context(_production_request(), db))
    assert error.value.status_code == 403
    assert error.value.detail == "ACCESS_DENIED"


def test_production_bearer_reaches_protected_routes_without_identity_headers(monkeypatch):
    """Bearer-only production requests must not depend on synthetic X-* headers."""
    from app.api.v1 import dependencies
    from app.core.database import get_db
    from app.main import app
    from app.models.widget_settings import WidgetSettings

    class FakeClient:
        async def get_account(self, account_url, access_token):
            return {"id": 20, "current_user_id": 10}

        async def list_users(self, account_url, access_token):
            return [{"id": 10, "rights": {"role_id": 77, "is_admin": True}}]

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setattr(dependencies, "AmoCRMClient", lambda http: FakeClient())
    db = _production_context_db(UserRole.ADMIN)
    db.add(WidgetSettings(account_id="20"))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    headers = {"Authorization": "Bearer access-token"}
    try:
        responses = [
            client.get("/api/v1/sessions/current/10", headers=headers),
            client.get("/api/v1/team/status", headers=headers),
            client.get("/api/v1/kpi/my", headers=headers),
            client.get(
                "/api/v1/reports/daily?account_id=20&date=2026-09-19",
                headers=headers,
            ),
            client.get("/api/v1/settings/snapshot", headers=headers),
        ]
        assert [response.status_code for response in responses] == [200] * 5
    finally:
        app.dependency_overrides.clear()


def test_production_route_rejects_forged_identity_headers_even_with_bearer(monkeypatch):
    """Client X-* values remain forbidden authentication transport in production."""
    from app.core.database import get_db
    from app.main import app

    monkeypatch.setenv("ENVIRONMENT", "production")
    db = _production_context_db(UserRole.EMPLOYEE)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/settings/snapshot",
            headers={
                "Authorization": "Bearer access-token",
                "X-User-Id": "10",
                "X-Account-Id": "20",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AMOCRM_TOKEN_EXPIRED"
    finally:
        app.dependency_overrides.clear()
