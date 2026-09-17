from app.core.time_utils import utc_now

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    ForeignKeyConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class CrmEvent(Base):
    """Normalized event received from amoCRM analytics."""

    __tablename__ = "crm_events"
    __table_args__ = (
        UniqueConstraint("account_id", "external_id", name="uq_crm_events_external_id"),
        ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["users.amocrm_account_id", "users.id"],
            name="fk_crm_events_account_user",
        ),
        CheckConstraint(
            "is_complete IN (0,1) AND (is_complete = 0 OR user_id IS NOT NULL)",
            name="ck_crm_events_attribution",
        ),
        CheckConstraint(
            "user_id IS NULL OR (author_amocrm_user_id IS NOT NULL AND author_amocrm_user_id > 0)",
            name="ck_crm_events_author",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=False, index=True)
    external_id = Column(String(255), nullable=False)
    author_amocrm_user_id = Column(
        Integer, nullable=True
    )  # raw external author; <=0 is system
    user_id = Column(Integer, nullable=True, index=True)  # attributed internal User.id
    user = relationship("User")
    event_type = Column(String(100), nullable=False, index=True)
    object_type = Column(String(50), nullable=True)
    object_id = Column(Integer, nullable=True)
    occurred_at = Column(DateTime, nullable=False, index=True)
    description = Column(String(1000), nullable=True)
    card_url = Column(String(1000), nullable=True)
    payload = Column(JSON, nullable=True)
    is_complete = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, nullable=False, default=utc_now)
