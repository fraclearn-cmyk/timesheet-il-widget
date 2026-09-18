"""Trusted request-context dependency; browser identity fields are never production auth."""

from __future__ import annotations

import os
from secrets import compare_digest

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.access_policy import RequestContext
from app.core.config import settings
from app.core.database import get_db
from app.integrations.amocrm_client import AmoCRMClient, AmoCRMClientError
from app.integrations.oauth import OAuthTokenCipher
from app.models.oauth_connection import OAuthConnection
from app.models.user import User


class RequestContextUnauthorized(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AMOCRM_TOKEN_EXPIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _environment() -> str:
    return os.getenv("ENVIRONMENT", settings.ENVIRONMENT).lower()


def resolve_legacy_test_context(
    db: Session, user_id: str | None, account_id: str | None
) -> RequestContext:
    """Compatibility adapter exclusively for hermetic tests; production always rejects it."""
    if _environment() not in {"test", "testing"}:
        raise RequestContextUnauthorized()
    try:
        external_user_id, external_account_id = int(user_id or ""), int(
            account_id or ""
        )
    except ValueError as error:
        raise RequestContextUnauthorized() from error
    user = (
        db.query(User)
        .filter(
            User.amocrm_user_id == external_user_id,
            User.amocrm_account_id == external_account_id,
            User.is_active.is_(True),
        )
        .one_or_none()
    )
    if user is None:
        raise RequestContextUnauthorized()
    return RequestContext(account_id=external_account_id, user=user)


async def get_request_context(
    request: Request, db: Session = Depends(get_db)
) -> RequestContext:
    """Resolve identity from verified OAuth state, with a test-only legacy adapter."""
    legacy_user = request.headers.get("X-User-Id")
    legacy_account = request.headers.get("X-Account-Id")
    if legacy_user is not None or legacy_account is not None:
        return resolve_legacy_test_context(db, legacy_user, legacy_account)
    authorization = request.headers.get("Authorization", "")
    scheme, _, access_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not access_token:
        raise RequestContextUnauthorized()
    cipher = OAuthTokenCipher.from_secret(settings.SECRET_KEY)
    connection = None
    for candidate in db.query(OAuthConnection).filter(
        OAuthConnection.is_active.is_(True)
    ):
        try:
            stored_token = cipher.decrypt(candidate.encrypted_access_token)
        except ValueError:
            continue
        if compare_digest(stored_token, access_token):
            connection = candidate
            break
    if connection is None:
        raise RequestContextUnauthorized()
    try:
        async with httpx.AsyncClient() as http:
            account = await AmoCRMClient(http).get_account(
                connection.account_url, access_token
            )
    except (AmoCRMClientError, httpx.HTTPError):
        raise RequestContextUnauthorized()
    account_id, user_id = account.get("id"), account.get("current_user_id")
    if (
        account_id != connection.account_id
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise RequestContextUnauthorized()
    user = (
        db.query(User)
        .filter(
            User.amocrm_account_id == account_id,
            User.amocrm_user_id == user_id,
            User.is_active.is_(True),
        )
        .one_or_none()
    )
    if user is None:
        raise RequestContextUnauthorized()
    context = RequestContext(account_id=account_id, user=user)
    _inject_legacy_compatibility_headers(request, context)
    return context


def _inject_legacy_compatibility_headers(
    request: Request, context: RequestContext
) -> None:
    """Feed legacy routes server-verified IDs without accepting client-supplied headers."""
    protected_names = {b"x-user-id", b"x-account-id"}
    headers = [
        (name, value)
        for name, value in request.scope["headers"]
        if name.lower() not in protected_names
    ]
    headers.extend(
        [
            (b"x-user-id", str(context.user.amocrm_user_id).encode()),
            (b"x-account-id", str(context.account_id).encode()),
        ]
    )
    request.scope["headers"] = headers
