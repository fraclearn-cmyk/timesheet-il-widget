from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class ActivityCategory(Base):
    """Activity category model - defines event categories with colors"""
    __tablename__ = "activity_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    
    color = Column(String(50), nullable=False)  # hex color or CSS color name
    icon = Column(String(50), nullable=True)
    
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    
    sort_order = Column(Integer, default=0)
    
    # Relationships
    events = relationship("ActivityEvent", back_populates="category")

    def __repr__(self):
        return f"<ActivityCategory(id={self.id}, name={self.name}, color={self.color})>"
