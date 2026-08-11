"""KPI and dashboard endpoints"""
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import RBACService, get_rbac_service
from app.schemas.kpi import KPIMetrics, ChartData, DashboardSettingsUpdate
from app.services.kpi_service import KPIService
from app.models.dashboard_settings import DashboardSettings

router = APIRouter()


@router.get("/my", response_model=KPIMetrics)
async def get_my_kpi(
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get my KPI metrics (all roles)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    service = KPIService(db)
    return service.calculate_user_kpi(user.id, user.amocrm_user_id)


@router.get("/user/{target_user_id}", response_model=KPIMetrics)
async def get_user_kpi(
    target_user_id: int,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get user KPI (ROP/Admin only)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user or rbac.is_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    from app.models.user import User
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not rbac.can_view_employee(user, target.department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this user")
    
    service = KPIService(db)
    return service.calculate_user_kpi(target.id, target.amocrm_user_id)


@router.get("/department/{dept_id}", response_model=KPIMetrics)
async def get_department_kpi(
    dept_id: int,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get department KPI (ROP/Admin only)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user or rbac.is_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    if not rbac.can_view_department(user, dept_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this department")
    
    service = KPIService(db)
    return service.calculate_department_kpi(dept_id)


@router.get("/chart/my", response_model=ChartData)
async def get_my_chart(
    days: int = Query(7, ge=1, le=30),
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get my chart data"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    service = KPIService(db)
    return service.get_chart_data(user.amocrm_user_id, days)


@router.get("/chart/user/{target_user_id}", response_model=ChartData)
async def get_user_chart(
    target_user_id: int,
    days: int = Query(7, ge=1, le=30),
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get user chart data (ROP/Admin only)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user or rbac.is_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    from app.models.user import User
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not rbac.can_view_employee(user, target.department_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this user")
    
    service = KPIService(db)
    return service.get_chart_data(target.amocrm_user_id, days)


@router.get("/chart/department/{dept_id}", response_model=ChartData)
async def get_department_chart(
    dept_id: int,
    days: int = Query(7, ge=1, le=30),
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get department chart data (ROP/Admin only)"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user or rbac.is_employee(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    if not rbac.can_view_department(user, dept_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access this department")
    
    service = KPIService(db)
    return service.get_department_chart_data(dept_id, days)


@router.get("/dashboard/settings")
async def get_dashboard_settings(
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Get dashboard settings"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    settings = db.query(DashboardSettings).filter(DashboardSettings.user_id == user.id).first()
    if not settings:
        # Return defaults
        return {
            "show_online": True,
            "show_late_arrivals": True,
            "show_team_stats": not rbac.is_employee(user),
            "default_period": "week",
            "chart_type": "line"
        }
    
    return settings


@router.put("/dashboard/settings")
async def update_dashboard_settings(
    updates: DashboardSettingsUpdate,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """Update dashboard settings"""
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    settings = db.query(DashboardSettings).filter(DashboardSettings.user_id == user.id).first()
    if not settings:
        settings = DashboardSettings(user_id=user.id)
        db.add(settings)
    
    # Update fields
    if updates.show_online is not None:
        settings.show_online = updates.show_online
    if updates.show_late_arrivals is not None:
        settings.show_late_arrivals = updates.show_late_arrivals
    if updates.show_team_stats is not None:
        settings.show_team_stats = updates.show_team_stats
    if updates.default_period is not None:
        settings.default_period = updates.default_period
    if updates.chart_type is not None:
        settings.chart_type = updates.chart_type
    
    db.commit()
    db.refresh(settings)
    
    return settings
