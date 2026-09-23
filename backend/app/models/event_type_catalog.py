from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.core.database import Base


class EventTypeCatalog(Base):
    """Last known amoCRM event-type catalog entry for one account."""

    __tablename__ = "event_type_catalog"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "event_key", name="uq_event_type_catalog_account_key"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("oauth_connections.account_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_key = Column(String(100), nullable=False)
    label = Column(String(255), nullable=True)
    refreshed_at = Column(DateTime, nullable=False, index=True)
