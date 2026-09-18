from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base
from app.core.time_utils import utc_now


class OAuthConnection(Base):
    """One encrypted server-side amoCRM OAuth connection per account."""

    __tablename__ = "oauth_connections"

    account_id = Column(Integer, primary_key=True)
    account_url = Column(String(255), nullable=False)
    account_name = Column(String(255), nullable=True)
    encrypted_access_token = Column(String, nullable=False)
    encrypted_refresh_token = Column(String, nullable=False)
    access_token_expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
