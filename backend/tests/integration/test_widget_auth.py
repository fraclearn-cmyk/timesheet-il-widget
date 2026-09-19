from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.widget_auth import decode_widget_token
from app.integrations.oauth import OAuthTokenCipher
from app.main import app
from app.models.oauth_connection import OAuthConnection
from app.models.user import User, UserRole
from app.models.widget_settings import WidgetSettings


ACCOUNT_ID = 20
USER_ID = 10
ACCOUNT_URL = "https://example.amocrm.ru"
WIDGET_AUDIENCE = "https://example.invalid"
SERVER_ACCESS_TOKEN = "synthetic-server-access-token"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def admin_user(db):
    user = User(
        id=1,
        amocrm_user_id=USER_ID,
        amocrm_account_id=ACCOUNT_ID,
        name="Synthetic admin",
        role=UserRole.ADMIN,
        amocrm_rights={"is_admin": False},
    )
    cipher = OAuthTokenCipher.from_secret(settings.SECRET_KEY)
    db.add_all(
        [
            user,
            OAuthConnection(
                account_id=ACCOUNT_ID,
                account_url=ACCOUNT_URL,
                encrypted_access_token=cipher.encrypt(SERVER_ACCESS_TOKEN),
                encrypted_refresh_token=cipher.encrypt("synthetic-server-refresh-token"),
            ),
            WidgetSettings(account_id=str(ACCOUNT_ID)),
        ]
    )
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def signed_widget_token():
    def sign(
        *,
        user_id: int = USER_ID,
        mutation: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "iss": ACCOUNT_URL,
            "aud": WIDGET_AUDIENCE,
            "jti": str(uuid4()),
            "iat": now,
            "nbf": now - timedelta(seconds=1),
            "exp": now + timedelta(minutes=5),
            "account_id": ACCOUNT_ID,
            "user_id": user_id,
            "client_uuid": settings.AMOCRM_CLIENT_ID,
        }
        secret = settings.AMOCRM_CLIENT_SECRET
        if mutation == "expired":
            payload["exp"] = now - timedelta(seconds=1)
        elif mutation == "wrong_audience":
            payload["aud"] = "https://other.invalid"
        elif mutation == "wrong_issuer":
            payload["iss"] = "https://other.amocrm.ru"
        elif mutation == "wrong_client":
            payload["client_uuid"] = "synthetic-other-client"
        elif mutation == "missing_audience":
            payload.pop("aud")
        elif mutation == "forged_signature":
            secret = "synthetic-forged-secret"
        elif mutation is not None:
            raise ValueError(f"unknown synthetic mutation: {mutation}")
        return jwt.encode(payload, secret, algorithm="HS256")

    return sign


@pytest.fixture
def live_amocrm(monkeypatch):
    from app.api.v1 import dependencies

    calls: list[tuple[str, str, str]] = []

    class FakeClient:
        async def get_account(self, account_url, access_token):
            calls.append(("account", account_url, access_token))
            return {"id": ACCOUNT_ID, "current_user_id": 999}

        async def list_users(self, account_url, access_token):
            calls.append(("users", account_url, access_token))
            return [
                {
                    "id": USER_ID,
                    "rights": {"role_id": 77, "is_admin": True},
                }
            ]

    monkeypatch.setattr(dependencies, "AmoCRMClient", lambda http: FakeClient())
    return calls


@pytest.fixture
def client(db, admin_user, live_amocrm):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "mutation",
    [
        "expired",
        "wrong_audience",
        "wrong_issuer",
        "wrong_client",
        "forged_signature",
    ],
)
def test_widget_token_rejects_untrusted_claims(
    client, signed_widget_token, mutation
):
    token = signed_widget_token(mutation=mutation)

    response = client.get(
        "/api/v1/settings/snapshot", headers={"X-Auth-Token": token}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AMO_WIDGET_TOKEN_INVALID"


def test_widget_token_builds_verified_context(
    client, signed_widget_token, admin_user, db, live_amocrm
):
    response = client.get(
        "/api/v1/settings/snapshot",
        headers={
            "X-Auth-Token": signed_widget_token(
                user_id=admin_user.amocrm_user_id
            )
        },
    )

    assert response.status_code == 200
    db.refresh(admin_user)
    assert admin_user.amocrm_rights == {"role_id": 77, "is_admin": True}
    assert admin_user.amocrm_role_id == 77
    assert live_amocrm == [
        ("account", ACCOUNT_URL, SERVER_ACCESS_TOKEN),
        ("users", ACCOUNT_URL, SERVER_ACCESS_TOKEN),
    ]


@pytest.mark.parametrize("inactive_model", ["connection", "user"])
def test_widget_token_requires_active_server_state(
    client, signed_widget_token, db, admin_user, inactive_model
):
    if inactive_model == "connection":
        db.get(OAuthConnection, ACCOUNT_ID).is_active = False
    else:
        admin_user.is_active = False
    db.commit()

    response = client.get(
        "/api/v1/settings/snapshot",
        headers={"X-Auth-Token": signed_widget_token()},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AMO_WIDGET_TOKEN_INVALID"


def test_widget_token_never_falls_back_to_browser_identity_headers(
    client, signed_widget_token
):
    response = client.get(
        "/api/v1/settings/snapshot",
        headers={
            "X-Auth-Token": signed_widget_token(mutation="wrong_audience"),
            "X-User-Id": str(USER_ID),
            "X-Account-Id": str(ACCOUNT_ID),
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AMO_WIDGET_TOKEN_INVALID"


def test_widget_token_requires_audience_before_live_or_snapshot_service(
    client, signed_widget_token, live_amocrm, monkeypatch
):
    from app.services.settings_snapshot_service import SettingsSnapshotService

    settings_calls: list[int] = []
    original_load = SettingsSnapshotService.load

    def tracked_load(service, context):
        settings_calls.append(context.account_id)
        return original_load(service, context)

    monkeypatch.setattr(SettingsSnapshotService, "load", tracked_load)

    response = client.get(
        "/api/v1/settings/snapshot",
        headers={"X-Auth-Token": signed_widget_token(mutation="missing_audience")},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AMO_WIDGET_TOKEN_INVALID"
    assert live_amocrm == []
    assert settings_calls == []


def test_widget_token_rejects_user_missing_from_live_amocrm(
    client, signed_widget_token, monkeypatch
):
    from app.api.v1 import dependencies

    class MissingUserClient:
        async def get_account(self, account_url, access_token):
            return {"id": ACCOUNT_ID, "current_user_id": 999}

        async def list_users(self, account_url, access_token):
            return []

    monkeypatch.setattr(
        dependencies, "AmoCRMClient", lambda http: MissingUserClient()
    )

    response = client.get(
        "/api/v1/settings/snapshot",
        headers={"X-Auth-Token": signed_widget_token()},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AMO_WIDGET_TOKEN_INVALID"


def test_decode_widget_token_rejects_missing_required_claims():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "iss": ACCOUNT_URL,
            "aud": WIDGET_AUDIENCE,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=5),
            "account_id": ACCOUNT_ID,
            "user_id": USER_ID,
            "client_uuid": settings.AMOCRM_CLIENT_ID,
        },
        settings.AMOCRM_CLIENT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(ValueError):
        decode_widget_token(
            token,
            secret=settings.AMOCRM_CLIENT_SECRET,
            audience=WIDGET_AUDIENCE,
            client_uuid=settings.AMOCRM_CLIENT_ID,
        )


@pytest.mark.parametrize(
    "origin",
    [
        "https://tenant.amocrm.ru",
        "https://tenant.amocrm.com",
        "https://tenant.kommo.com",
    ],
)
def test_cors_allows_widget_token_from_single_label_tenant_origins(origin):
    with TestClient(app) as test_client:
        response = test_client.options(
            "/api/v1/settings/snapshot",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Auth-Token",
            },
        )

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == origin
    assert "x-auth-token" in response.headers["Access-Control-Allow-Headers"].lower()


@pytest.mark.parametrize(
    "origin",
    [
        "http://tenant.amocrm.ru",
        "https://amocrm.ru",
        "https://nested.tenant.amocrm.ru",
        "https://tenant.amocrm.ru.attacker.invalid",
    ],
)
def test_cors_rejects_non_tenant_origins(origin):
    with TestClient(app) as test_client:
        response = test_client.options(
            "/api/v1/settings/snapshot",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Auth-Token",
            },
        )

    assert response.status_code == 400
    assert "Access-Control-Allow-Origin" not in response.headers
