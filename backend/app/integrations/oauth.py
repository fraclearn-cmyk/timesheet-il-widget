"""OAuth storage helpers. Diagnostics are intentionally token-free."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.time_utils import utc_now
from app.integrations.amocrm_contract import AmoCRMAuthClient, AmoCRMTokens
from app.models.oauth_connection import OAuthConnection


def mask_secret(value: str | None) -> str:
    if not value:
        return "<missing>"
    return "***" + value[-4:]


class OAuthTokenCipher:
    """Encrypt OAuth values with a Fernet key derived from configured secret material."""

    def __init__(self, fernet: Fernet) -> None:
        self._fernet = fernet

    @classmethod
    def from_secret(cls, secret_material: str) -> "OAuthTokenCipher":
        if len(secret_material) < 32:
            raise ValueError("OAuth encryption key material is too short")
        key = base64.urlsafe_b64encode(
            hashlib.sha256(secret_material.encode()).digest()
        )
        return cls(Fernet(key))

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except (InvalidToken, UnicodeDecodeError) as error:
            raise ValueError("stored OAuth token cannot be decrypted") from error


@dataclass(frozen=True)
class StoredOAuthConnection:
    account_id: int
    access_token: str
    refresh_token: str


class OAuthService:
    """Persist an OAuth pair atomically only after a complete successful grant."""

    def __init__(
        self, db: Session, client: AmoCRMAuthClient, cipher: OAuthTokenCipher
    ) -> None:
        self._db, self._client, self._cipher = db, client, cipher

    def exchange_code(self, account_url: str, code: str) -> OAuthConnection:
        tokens = self._client.exchange_authorization_code(account_url, code)
        account = self._client.get_account_context(
            account_url, access_token=tokens.access_token
        )
        return self._store_tokens(account_url, account, tokens)

    def refresh(self, connection: OAuthConnection) -> OAuthConnection:
        refresh_token = self._cipher.decrypt(connection.encrypted_refresh_token)
        tokens = self._client.refresh_access_token(
            connection.account_url, refresh_token
        )
        return self._store_tokens(
            connection.account_url, {"id": connection.account_id}, tokens
        )

    def load_tokens(self, connection: OAuthConnection) -> StoredOAuthConnection:
        return StoredOAuthConnection(
            connection.account_id,
            self._cipher.decrypt(connection.encrypted_access_token),
            self._cipher.decrypt(connection.encrypted_refresh_token),
        )

    def _store_tokens(
        self, account_url: str, account: object, tokens: AmoCRMTokens
    ) -> OAuthConnection:
        if (
            not isinstance(account, dict)
            or not isinstance(account.get("id"), int)
            or account["id"] <= 0
        ):
            raise ValueError("amoCRM account response lacks a valid account ID")
        connection = self._db.get(OAuthConnection, account["id"])
        if connection is None:
            connection = OAuthConnection(
                account_id=account["id"], account_url=account_url
            )
            self._db.add(connection)
        connection.account_url = account_url
        connection.account_name = (
            account.get("name") if isinstance(account.get("name"), str) else None
        )
        connection.encrypted_access_token = self._cipher.encrypt(tokens.access_token)
        connection.encrypted_refresh_token = self._cipher.encrypt(tokens.refresh_token)
        connection.access_token_expires_at = utc_now() + timedelta(
            seconds=tokens.expires_in
        )
        connection.is_active = True
        self._db.commit()
        self._db.refresh(connection)
        return connection
