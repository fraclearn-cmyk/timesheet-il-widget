"""Hermetic test configuration; no application database or live credentials."""

import os

os.environ.update(
    DATABASE_URL="sqlite://",
    DEBUG="false",
    ENVIRONMENT="test",
    AMOCRM_CLIENT_ID="synthetic-client-id",
    AMOCRM_CLIENT_SECRET="synthetic-client-secret",
    AMOCRM_REDIRECT_URI="https://example.invalid/callback",
    SECRET_KEY="synthetic-test-key-with-at-least-32-characters",
)
