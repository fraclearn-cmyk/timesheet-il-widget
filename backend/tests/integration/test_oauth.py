import asyncio

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.integrations.amocrm_client import (
    AmoCRMClient,
    AmoCRMClientError,
    AmoCRMRateLimited,
)
from app.integrations.oauth import OAuthTokenCipher, mask_secret
from app.core.database import Base
from app.integrations.amocrm_contract import AmoCRMAuthClient, AmoCRMTokenExpired
from app.integrations.oauth import OAuthService
from app.models.oauth_connection import OAuthConnection


def test_mask_secret_never_exposes_the_original_token():
    """A diagnostic change that logs the token instead of its mask must fail."""
    token = "access-token-that-must-not-appear-in-diagnostics"

    masked = mask_secret(token)

    assert token not in masked
    assert masked.endswith(token[-4:])


def test_token_cipher_round_trip_keeps_plaintext_out_of_the_stored_value():
    """Replacing encryption with plain storage must make this safety check fail."""
    cipher = OAuthTokenCipher.from_secret(
        "synthetic-test-key-with-at-least-32-characters"
    )
    token = "refresh-token-for-test-only"

    encrypted = cipher.encrypt(token)

    assert token not in encrypted
    assert cipher.decrypt(encrypted) == token


def test_client_retries_a_transient_failure_then_returns_json():
    """Removing bounded retry would surface the first 503 instead of the response."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"id": 7}, request=request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = AmoCRMClient(http, max_retries=1, backoff_seconds=0)
            return await client.get_json("https://example.amocrm.ru/api/v4/account")

    assert asyncio.run(scenario()) == {"id": 7}
    assert calls == 2


def test_client_uses_retry_after_for_rate_limits_without_unbounded_retry():
    """Ignoring 429 or endlessly retrying must fail this deterministic limit."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "0"}, request=request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = AmoCRMClient(http, max_retries=1, backoff_seconds=0)
            with pytest.raises(AmoCRMRateLimited):
                await client.get_json("https://example.amocrm.ru/api/v4/users")

    asyncio.run(scenario())
    assert calls == 2


def test_user_pagination_stops_at_the_configured_page_budget():
    """Removing a page cap must not permit an upstream next-link chain to run forever."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "_embedded": {"users": [{"id": calls}]},
                "_links": {
                    "next": {"href": "https://example.amocrm.ru/api/v4/users?page=99"}
                },
            },
            request=request,
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = AmoCRMClient(http, max_pages=1, max_items=10)
            with pytest.raises(AmoCRMClientError):
                await client.list_users("https://example.amocrm.ru", "test-token")

    asyncio.run(scenario())
    assert calls == 1


def test_code_exchange_persists_only_encrypted_complete_token_pair():
    """A plaintext or partial authorization-code result must not become a connection."""
    responses = [
        httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 60,
            },
        ),
        httpx.Response(200, json={"id": 77, "name": "Account"}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        response.request = request
        return response

    db = sessionmaker(bind=create_engine("sqlite://"))()
    Base.metadata.create_all(db.bind)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = AmoCRMAuthClient(
            client_id="synthetic-client-id",
            client_secret="synthetic-client-secret",
            redirect_uri="https://example.invalid/callback",
            http_client=http,
        )
        service = OAuthService(
            db,
            client,
            OAuthTokenCipher.from_secret(
                "synthetic-test-key-with-at-least-32-characters"
            ),
        )
        stored = service.exchange_code(
            "https://example.amocrm.ru", "authorization-code"
        )

    assert stored.account_id == 77
    assert "new-access" not in stored.encrypted_access_token
    assert "new-refresh" not in stored.encrypted_refresh_token


def test_failed_refresh_keeps_the_previous_encrypted_pair():
    """Writing before a failed refresh would destroy the last usable connection."""
    db = sessionmaker(bind=create_engine("sqlite://"))()
    Base.metadata.create_all(db.bind)
    cipher = OAuthTokenCipher.from_secret(
        "synthetic-test-key-with-at-least-32-characters"
    )
    connection = OAuthConnection(
        account_id=77,
        account_url="https://example.amocrm.ru",
        encrypted_access_token=cipher.encrypt("old-access"),
        encrypted_refresh_token=cipher.encrypt("old-refresh"),
    )
    db.add(connection)
    db.commit()

    class FailingClient:
        def refresh_access_token(self, account_url, refresh_token):
            raise AmoCRMTokenExpired("refresh rejected")

    with pytest.raises(AmoCRMTokenExpired):
        OAuthService(db, FailingClient(), cipher).refresh(connection)

    db.refresh(connection)
    assert cipher.decrypt(connection.encrypted_access_token) == "old-access"
    assert cipher.decrypt(connection.encrypted_refresh_token) == "old-refresh"


def test_partial_refresh_response_keeps_the_previous_encrypted_pair():
    """A partial OAuth response must not rotate either side of the stored pair."""
    db = sessionmaker(bind=create_engine("sqlite://"))()
    Base.metadata.create_all(db.bind)
    cipher = OAuthTokenCipher.from_secret(
        "synthetic-test-key-with-at-least-32-characters"
    )
    connection = OAuthConnection(
        account_id=78,
        account_url="https://example.amocrm.ru",
        encrypted_access_token=cipher.encrypt("old-access"),
        encrypted_refresh_token=cipher.encrypt("old-refresh"),
    )
    db.add(connection)
    db.commit()

    responses = [
        httpx.Response(200, json={"access_token": "new-access", "expires_in": 60})
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        response.request = request
        return response

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = AmoCRMAuthClient(
            client_id="synthetic-client-id",
            client_secret="synthetic-client-secret",
            redirect_uri="https://example.invalid/callback",
            http_client=http,
        )
        with pytest.raises(AmoCRMTokenExpired):
            OAuthService(db, client, cipher).refresh(connection)

    db.refresh(connection)
    assert cipher.decrypt(connection.encrypted_access_token) == "old-access"
    assert cipher.decrypt(connection.encrypted_refresh_token) == "old-refresh"
