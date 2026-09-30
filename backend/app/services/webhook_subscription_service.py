"""Server-side amoCRM webhook destination reconciliation."""

from __future__ import annotations

import hashlib
import secrets
from typing import Protocol, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.oauth import OAuthTokenCipher
from app.models import IngestionCursor, OAuthConnection


class WebhookURLMissing(RuntimeError):
    pass


class WebhookClient(Protocol):
    async def ensure_webhook(
        self,
        account_url: str,
        access_token: str,
        *,
        destination: str,
        settings: Sequence[str],
    ) -> None: ...


class WebhookSubscriptionService:
    """Register the provider-compatible opaque callback destination.

    amoCRM's supported webhook contract has no verifiable HMAC header. A fresh
    ``token_urlsafe(32)`` path supplies 256 bits of entropy; only its SHA-256
    digest is used for ingress lookup, while the encrypted value is retained
    solely so server-side reconciliation can reproduce the destination.
    """

    SETTINGS = (
        "add_lead",
        "update_lead",
        "add_contact",
        "update_contact",
        "add_company",
        "update_company",
        "add_task",
        "update_task",
    )

    def __init__(
        self,
        db: Session,
        client: WebhookClient,
        cipher: OAuthTokenCipher,
        *,
        public_base_url: str | None,
        clock,
    ) -> None:
        self._db = db
        self._client = client
        self._cipher = cipher
        self._public_base_url = public_base_url
        self._clock = clock

    async def ensure(self, account_id: int) -> bool:
        if not self._public_base_url:
            raise WebhookURLMissing("public webhook URL is not configured")
        try:
            # OAuthConnection always exists before an ingestion cursor and is the
            # durable per-account serialization row for first-time hook creation.
            connection = self._db.scalar(
                select(OAuthConnection)
                .where(OAuthConnection.account_id == account_id)
                .with_for_update()
            )
            if connection is None or not connection.is_active:
                raise LookupError("active OAuth connection not found")
            cursor = self._db.scalar(
                select(IngestionCursor)
                .where(IngestionCursor.account_id == account_id)
                .with_for_update()
            )
            if cursor is None:
                cursor = IngestionCursor(
                    account_id=account_id, next_poll_at=self._clock()
                )
                self._db.add(cursor)
                self._db.flush()
            if cursor.encrypted_webhook_key is None:
                hook_id = secrets.token_urlsafe(32)
                cursor.webhook_key_hash = hashlib.sha256(hook_id.encode()).hexdigest()
                cursor.encrypted_webhook_key = self._cipher.encrypt(hook_id)
            else:
                hook_id = self._cipher.decrypt(cursor.encrypted_webhook_key)
                expected_hash = hashlib.sha256(hook_id.encode()).hexdigest()
                if cursor.webhook_key_hash != expected_hash:
                    raise ValueError("stored webhook key hash does not match")
            account_url = connection.account_url
            access_token = self._cipher.decrypt(connection.encrypted_access_token)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        destination = f"{self._public_base_url}/api/v1/webhooks/amocrm/{hook_id}"
        await self._client.ensure_webhook(
            account_url,
            access_token,
            destination=destination,
            settings=self.SETTINGS,
        )
        return True
