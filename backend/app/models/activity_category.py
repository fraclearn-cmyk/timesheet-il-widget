from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class ActivityCategory(Base):
    """Activity category model - defines event categories with colors"""

    __tablename__ = "activity_categories"
    __table_args__ = (
        UniqueConstraint(
            "account_id", "name", name="uq_activity_categories_account_name"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    # Added in migration 007.  NULL is retained only for legacy rows whose
    # account cannot be proven from historical activity; new rows always set it.
    account_id = Column(Integer, nullable=True, index=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(200), nullable=False)

    color = Column(String(50), nullable=False)  # hex color or CSS color name
    icon = Column(String(50), nullable=True)

    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    sort_order = Column(Integer, nullable=False, default=0, server_default="0")

    # Relationships
    events = relationship("ActivityEvent", back_populates="category")

    def __repr__(self):
        return f"<ActivityCategory(id={self.id}, name={self.name}, color={self.color})>"
