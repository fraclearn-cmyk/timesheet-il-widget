"""KPI and charts schemas"""
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class KPIMetrics(BaseModel):
    """User or department KPI metrics"""
    # Time metrics
    hours_today: float
    hours_week: float
    hours_month: float
    avg_hours_per_day: float
    
    # Performance
    late_count_week: int
    late_count_month: int
    completion_percentage: float  # % of norm
    
    # Status
    current_status: str  # working, break, finished, offline
    is_online: bool
    
    # Optional for department
    total_employees: Optional[int] = None
    online_now: Optional[int] = None


class ChartDataPoint(BaseModel):
    """Single data point for chart"""
    date: str  # YYYY-MM-DD
    value: float
    label: Optional[str] = None


class ChartData(BaseModel):
    """Chart data with multiple series"""
    labels: List[str]  # X-axis labels (dates)
    datasets: List[dict]  # Chart.js format datasets
    

class DashboardSettingsUpdate(BaseModel):
    """Update dashboard settings"""
    show_online: Optional[bool] = None
    show_late_arrivals: Optional[bool] = None
    show_team_stats: Optional[bool] = None
    default_period: Optional[str] = None  # week, month
    chart_type: Optional[str] = None  # line, bar


class KPIPeriodRequest(BaseModel):
    """Request for KPI with period"""
    days: int = 7  # 7 or 30
