"""Hermetic test configuration; no application database or live credentials."""

import os

import pytest

os.environ.update(
    DATABASE_URL="sqlite://",
    DEBUG="false",
    ENVIRONMENT="test",
    AMOCRM_CLIENT_ID="synthetic-client-id",
    AMOCRM_CLIENT_SECRET="synthetic-client-secret",
    AMOCRM_REDIRECT_URI="https://example.invalid/callback",
    SECRET_KEY="synthetic-test-key-with-at-least-32-characters",
    INGESTION_WORKER_ENABLED="false",
)


@pytest.fixture(autouse=True)
def isolate_process_local_ingress_limits():
    """Keep process-local production counters from leaking across test cases."""
    from app.api.v1 import webhooks
    from app.core.rate_limit import (
        authenticated_request_limiter,
        authentication_concurrency_guard,
        unknown_request_limiter,
    )

    authenticated_request_limiter.reset()
    unknown_request_limiter.reset()
    authentication_concurrency_guard.reset()
    webhooks.reset_webhook_rate_limits()
    yield
    authenticated_request_limiter.reset()
    unknown_request_limiter.reset()
    authentication_concurrency_guard.reset()
    webhooks.reset_webhook_rate_limits()
