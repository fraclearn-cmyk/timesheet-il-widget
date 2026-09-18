import asyncio

import httpx
import pytest

from app.integrations.amocrm_client import AmoCRMClient, AmoCRMRateLimited
from app.integrations.oauth import OAuthTokenCipher, mask_secret


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
