from sqlalchemy import Column, Integer, String, JSON, Boolean, DateTime
from app.core.time_utils import utc_now
from app.core.database import Base


class WidgetSettings(Base):
    """Widget settings model - stores widget configuration per account"""

    __tablename__ = "widget_settings"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer, unique=True, nullable=False, index=True
    )  # amoCRM account ID
    account_name = Column(String(255), nullable=True)

    # General settings
    polling_interval = Column(Integer, nullable=False, default=15)  # seconds
    inactivity_timeout = Column(
        Integer, nullable=False, default=300
    )  # seconds (5 minutes)

    # Feature flags
    enable_activity_tracking = Column(Boolean, nullable=False, default=True)
    enable_overlay_blocking = Column(Boolean, nullable=False, default=True)
    enable_auto_finish = Column(Boolean, nullable=False, default=False)

    # Excel export settings
    excel_columns = Column(JSON, nullable=True)  # List of enabled columns

    # Additional settings as JSON
    settings = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<WidgetSettings(id={self.id}, account_id={self.account_id})>"
