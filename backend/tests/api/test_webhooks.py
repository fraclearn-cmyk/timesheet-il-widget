from datetime import datetime, timedelta
import hashlib
import io
import logging

import pytest
import httpx
from fastapi.testclient import TestClient
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.dependencies import get_request_context
from app.core.access_policy import RequestContext
from app.core.database import Base, get_db
from app.models import IngestionCursor, OAuthConnection, User
from app.integrations.oauth import OAuthTokenCipher
from app.services.webhook_subscription_service import WebhookSubscriptionService


NOW = datetime(2026, 9, 23, 9)
HOOK = "h" * 43


@pytest.fixture
def webhook_api(monkeypatch):
    from app.main import app
    from app.api.v1 import webhooks

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = User(
        id=1,
        amocrm_user_id=101,
        amocrm_account_id=10,
        name="Admin",
        amocrm_rights={"is_admin": True},
    )
    employee = User(
        id=2,
        amocrm_user_id=102,
        amocrm_account_id=10,
        name="Employee",
        amocrm_rights={"is_admin": False},
    )
    db.add_all(
        [
            admin,
            employee,
            OAuthConnection(
                account_id=10,
                account_url="https://tenant.amocrm.ru",
                encrypted_access_token="encrypted-access",
                encrypted_refresh_token="encrypted-refresh",
            ),
            IngestionCursor(
                account_id=10,
                next_poll_at=NOW + timedelta(minutes=1),
                webhook_key_hash=hashlib.sha256(HOOK.encode()).hexdigest(),
                encrypted_webhook_key="encrypted-hook",
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(webhooks, "utc_now", lambda: NOW)
    webhooks.reset_webhook_rate_limits()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_request_context] = lambda: RequestContext(10, admin)
    with TestClient(app) as client:
        yield client, db, app, admin, employee
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_unknown_webhook_is_indistinguishable_and_changes_nothing(webhook_api):
    client, db, _, _, _ = webhook_api
    before = db.get(IngestionCursor, 10).next_poll_at
    response = client.post("/api/v1/webhooks/amocrm/unknown", content=b"anything")
    assert response.status_code == 202
    assert response.json() == {"accepted": True}
    db.expire_all()
    assert db.get(IngestionCursor, 10).next_poll_at == before


def test_valid_webhook_only_advances_poll_and_never_persists_payload(webhook_api):
    from app.models import ActivityInterval, CrmEvent, RawIngestionEvent

    client, db, _, _, _ = webhook_api
    response = client.post(
        f"/api/v1/webhooks/amocrm/{HOOK}",
        json={"id": "forged", "text": "secret", "created_by": 101},
    )
    assert response.status_code == 202
    db.expire_all()
    assert db.get(IngestionCursor, 10).next_poll_at == NOW
    assert db.query(RawIngestionEvent).count() == 0
    assert db.query(CrmEvent).count() == 0
    assert db.query(ActivityInterval).count() == 0


def test_webhook_repetition_and_oversized_bodies_are_bounded(webhook_api):
    client, _, _, _, _ = webhook_api
    rate_request_id = "33445c1e-e101-403c-af74-6d55f9e725f9"
    oversized_request_id = "c1690a7d-4e60-4c92-ad9a-605d0b157561"
    for _ in range(10):
        assert (
            client.post(f"/api/v1/webhooks/amocrm/{HOOK}", content=b"x").status_code
            == 202
        )
    limited = client.post(
        f"/api/v1/webhooks/amocrm/{HOOK}",
        content=b"x",
        headers={"X-Request-Id": rate_request_id},
    )
    oversized = client.post(
        "/api/v1/webhooks/amocrm/different",
        content=b"x" * (64 * 1024 + 1),
        headers={"X-Request-Id": oversized_request_id},
    )
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert limited.json() == {
        "error": {
            "code": "RATE_LIMITED",
            "message": "Слишком много запросов.",
            "request_id": rate_request_id,
        }
    }
    assert limited.headers["X-Request-Id"] == rate_request_id
    assert oversized.status_code == 413
    assert oversized.json() == {
        "error": {
            "code": "PAYLOAD_TOO_LARGE",
            "message": "Размер запроса превышает 64 КиБ.",
            "request_id": oversized_request_id,
        }
    }
    assert oversized.headers["X-Request-Id"] == oversized_request_id


def test_webhook_rate_limit_bucket_count_is_bounded():
    from app.api.v1 import webhooks

    webhooks.reset_webhook_rate_limits()
    for index in range(webhooks._MAX_RATE_BUCKETS + 100):
        assert webhooks._limited(str(index), 1.0) is False
    assert len(webhooks._requests) <= webhooks._MAX_RATE_BUCKETS


@pytest.mark.asyncio
async def test_webhook_body_limit_streams_without_aggregating_unbounded_input():
    from app.api.v1.webhooks import _body_within_limit

    chunks = iter([b"x" * 32_768, b"y" * 32_768, b"z"])

    async def receive():
        try:
            chunk = next(chunks)
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.request", "body": chunk, "more_body": True}

    request = Request({"type": "http", "method": "POST", "path": "/"}, receive)
    assert await _body_within_limit(request, 64 * 1024) is False


def test_hook_id_never_enters_application_logs(webhook_api, caplog):
    client, _, _, _, _ = webhook_api
    with caplog.at_level("DEBUG"):
        assert (
            client.post(f"/api/v1/webhooks/amocrm/{HOOK}", content=b"x").status_code
            == 202
        )
    application_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("app")
    )
    assert HOOK not in application_logs


def test_hook_id_is_redacted_by_uvicorn_access_formatter():
    from uvicorn.logging import AccessFormatter
    from app.core.logging import WebhookAccessLogFilter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s')
    )
    logger = logging.Logger("uvicorn.access.regression")
    logger.addFilter(WebhookAccessLogFilter())
    logger.addHandler(handler)

    logger.info(
        '%s - "%s %s HTTP/%s" %d',
        "127.0.0.1:1",
        "POST",
        f"/api/v1/webhooks/amocrm/{HOOK}",
        "1.1",
        202,
    )

    assert HOOK not in stream.getvalue()
    assert "/api/v1/webhooks/amocrm/[redacted]" in stream.getvalue()


def test_global_rate_limiter_bounds_distinct_clients():
    from app.main import RateLimitMiddleware

    limiter = RateLimitMiddleware(lambda scope, receive, send: None, max_clients=16)
    for index in range(100):
        limiter.record_request(f"192.0.2.{index}", now=1.0)
    assert len(limiter.requests) == 16


def test_webhook_ensure_requires_verified_admin(webhook_api):
    client, _, app, _, employee = webhook_api
    app.dependency_overrides[get_request_context] = lambda: RequestContext(10, employee)
    response = client.post("/api/v1/activity/ingestion/webhook/ensure")
    assert response.status_code == 403


def test_webhook_ensure_reports_missing_public_url(webhook_api, monkeypatch):
    from app.api.v1 import activity

    client, _, _, _, _ = webhook_api
    monkeypatch.setattr(activity.settings, "PUBLIC_BASE_URL", None)
    response = client.post("/api/v1/activity/ingestion/webhook/ensure")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WEBHOOK_URL_MISSING"


def test_admin_webhook_ensure_is_idempotent_and_hides_hook(webhook_api, monkeypatch):
    from app.api.v1 import activity

    class FakeService:
        calls = []

        async def ensure(self, account_id):
            self.calls.append(account_id)
            return True

    service = FakeService()
    client, _, app, _, _ = webhook_api
    monkeypatch.setattr(activity.settings, "PUBLIC_BASE_URL", "https://public.example")
    app.dependency_overrides[activity.get_webhook_subscription_service] = (
        lambda: service
    )
    first = client.post("/api/v1/activity/ingestion/webhook/ensure")
    second = client.post("/api/v1/activity/ingestion/webhook/ensure")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json() == {"enabled": True}
    assert HOOK not in first.text + second.text
    assert service.calls == [10, 10]


@pytest.mark.asyncio
async def test_subscription_service_generates_one_encrypted_256_bit_hook(webhook_api):
    class FakeClient:
        def __init__(self):
            self.calls = []

        async def ensure_webhook(self, account_url, access_token, **payload):
            self.calls.append((account_url, access_token, payload))

    _, db, _, _, _ = webhook_api
    cipher = OAuthTokenCipher.from_secret(
        "synthetic-test-key-with-at-least-32-characters"
    )
    connection = db.get(OAuthConnection, 10)
    connection.encrypted_access_token = cipher.encrypt("server-access-token")
    cursor = db.get(IngestionCursor, 10)
    cursor.webhook_key_hash = None
    cursor.encrypted_webhook_key = None
    db.commit()
    client = FakeClient()
    service = WebhookSubscriptionService(
        db,
        client,
        cipher,
        public_base_url="https://public.example",
        clock=lambda: NOW,
    )

    assert await service.ensure(10) is True
    first_encrypted = cursor.encrypted_webhook_key
    assert await service.ensure(10) is True

    db.refresh(cursor)
    hook_id = cipher.decrypt(cursor.encrypted_webhook_key)
    assert len(hashlib.sha256(hook_id.encode()).digest()) == 32
    assert cursor.webhook_key_hash == hashlib.sha256(hook_id.encode()).hexdigest()
    assert hook_id not in first_encrypted
    assert cursor.encrypted_webhook_key == first_encrypted
    assert [call[1] for call in client.calls] == ["server-access-token"] * 2
    destinations = [call[2]["destination"] for call in client.calls]
    assert (
        destinations == [f"https://public.example/api/v1/webhooks/amocrm/{hook_id}"] * 2
    )


@pytest.mark.asyncio
async def test_amocrm_webhook_reconciliation_skips_an_exact_existing_subscription():
    destination = "https://public.example/api/v1/webhooks/amocrm/opaque"
    desired = ["add_lead", "update_lead"]
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "_embedded": {
                    "webhooks": [
                        {
                            "destination": destination,
                            "settings": desired,
                            "disabled": False,
                        }
                    ]
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        from app.integrations.amocrm_client import AmoCRMClient

        await AmoCRMClient(transport).ensure_webhook(
            "https://tenant.amocrm.ru",
            "server-token",
            destination=destination,
            settings=desired,
        )
    assert [request.method for request in requests] == ["GET"]


@pytest.mark.asyncio
async def test_amocrm_webhook_reconciliation_updates_changed_settings():
    destination = "https://public.example/api/v1/webhooks/amocrm/opaque"
    requests = []

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "_embedded": {
                        "webhooks": [
                            {
                                "destination": destination,
                                "settings": ["add_lead"],
                                "disabled": False,
                            }
                        ]
                    }
                },
            )
        return httpx.Response(201, json={"destination": destination})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as transport:
        from app.integrations.amocrm_client import AmoCRMClient

        await AmoCRMClient(transport).ensure_webhook(
            "https://tenant.amocrm.ru",
            "server-token",
            destination=destination,
            settings=["add_lead", "update_lead"],
        )
    assert [request.method for request in requests] == ["GET", "POST"]
