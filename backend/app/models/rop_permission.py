from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class RopPermission(Base):
    """ROP Permission model - links ROPs to departments they can manage"""
    __tablename__ = "rop_permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="rop_permissions")

    def __repr__(self):
        return f"<RopPermission(user_id={self.user_id}, department_id={self.department_id})>"
