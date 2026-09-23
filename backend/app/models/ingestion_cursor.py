from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base


class IngestionCursor(Base):
    """Per-account polling watermark, schedule, lease and webhook lookup."""

    __tablename__ = "ingestion_cursors"
    __table_args__ = (
        CheckConstraint(
            "failure_count >= 0", name="ck_ingestion_cursors_failure_count"
        ),
        CheckConstraint(
            "webhook_key_hash IS NULL OR "
            "(length(webhook_key_hash) = 64 AND webhook_key_hash = lower(webhook_key_hash))",
            name="ck_ingestion_cursors_webhook_hash",
        ),
    )

    account_id = Column(
        Integer, ForeignKey("oauth_connections.account_id"), primary_key=True
    )
    last_created_at = Column(DateTime, nullable=True)
    last_event_id = Column(String(255), nullable=True)
    next_poll_at = Column(DateTime, nullable=False, index=True)
    last_success_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, nullable=False, default=0, server_default="0")
    lease_owner = Column(String(128), nullable=True)
    lease_until = Column(DateTime, nullable=True, index=True)
    webhook_key_hash = Column(String(64), nullable=True, unique=True)
    encrypted_webhook_key = Column(String, nullable=True)
