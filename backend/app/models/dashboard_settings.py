from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class DashboardSettings(Base):
    """Dashboard Settings model - personal KPI and chart settings for ROP/Admin"""
    __tablename__ = "dashboard_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Selected KPIs (array of KPI names)
    selected_kpis = Column(JSON, default=list)  # ["employees_working", "on_break", "finished", "total_hours"]
    
    # Chart settings
    chart_metric = Column(String(50), default="work_time")  # work_time, breaks, activity, employees, late
    chart_period = Column(String(20), default="day")  # day, week, month
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="dashboard_settings")

    def __repr__(self):
        return f"<DashboardSettings(user_id={self.user_id}, kpis={len(self.selected_kpis or [])})>"
