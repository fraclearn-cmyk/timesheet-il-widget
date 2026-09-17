from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from app.core.time_utils import utc_now
from app.core.database import Base


class StatusTransition(Base):
    """Status transition model - tracks status changes history"""

    __tablename__ = "status_transitions"
    __table_args__ = (
        CheckConstraint(
            "to_status IN ('working','break','finished') AND (from_status IS NULL OR from_status IN ('working','break','finished'))",
            name="ck_status_transitions_status",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    work_session_id = Column(
        Integer, ForeignKey("work_sessions.id", ondelete="CASCADE"), nullable=False
    )

    from_status = Column(String(50), nullable=True)  # NULL for first transition
    to_status = Column(String(50), nullable=False)

    timestamp = Column(DateTime, nullable=False, default=utc_now)
    duration = Column(Integer, nullable=True)  # seconds in previous status

    # Optional metadata
    reason = Column(String(255), nullable=True)
    notes = Column(String(1000), nullable=True)

    # Relationships
    work_session = relationship("WorkSession", back_populates="status_transitions")

    def __repr__(self):
        return f"<StatusTransition(id={self.id}, {self.from_status}->{self.to_status})>"
