from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    UniqueConstraint,
    Uuid,
)

from app.core.database import Base


class PresenceBatch(Base):
    """Aggregated, content-free browser presence signal."""

    __tablename__ = "presence_batches"
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "user_id",
            "command_id",
            name="uq_presence_batches_scope_command",
        ),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["users.amocrm_account_id", "users.id"],
            name="fk_presence_batches_account_user",
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "signal_count BETWEEN 1 AND 100000",
            name="ck_presence_batches_signal_count",
        ),
        CheckConstraint(
            "last_seen_at >= window_started_at",
            name="ck_presence_batches_window",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    command_id = Column(Uuid(as_uuid=True), nullable=False)
    window_started_at = Column(DateTime, nullable=False, index=True)
    last_seen_at = Column(DateTime, nullable=False)
    signal_count = Column(Integer, nullable=False)
