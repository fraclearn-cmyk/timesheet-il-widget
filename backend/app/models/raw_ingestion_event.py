from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)

from app.core.database import Base


class RawIngestionEvent(Base):
    """Short-lived source envelope retained separately from normalized data."""

    __tablename__ = "raw_ingestion_events"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "source",
            "dedup_key",
            name="uq_raw_ingestion_events_scope_dedup",
        ),
        CheckConstraint(
            "source IN ('crm_event','call')",
            name="ck_raw_ingestion_events_source",
        ),
        CheckConstraint(
            "normalization_status IN ('pending','complete','incomplete')",
            name="ck_raw_ingestion_events_status",
        ),
        CheckConstraint(
            "length(dedup_key) = 64 AND dedup_key = lower(dedup_key)",
            name="ck_raw_ingestion_events_dedup_key",
        ),
        CheckConstraint(
            "expires_at >= received_at",
            name="ck_raw_ingestion_events_expiry",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("oauth_connections.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(String(30), nullable=False)
    external_id = Column(String(255), nullable=True)
    occurred_at = Column(DateTime, nullable=True, index=True)
    dedup_key = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    received_at = Column(DateTime, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    normalization_status = Column(String(30), nullable=False, index=True)
    error_code = Column(String(100), nullable=True)
