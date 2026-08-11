"""Excel export endpoints"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date

from app.core.database import get_db
from app.core.rbac import RBACService, get_rbac_service
from app.schemas.excel import ExcelExportRequest
from app.services.excel_service import ExcelService

router = APIRouter()


@router.post("/department")
async def export_department_report(
    request: ExcelExportRequest,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Export department report to Excel.
    Only ROP and Admin can export.
    ROP can only export their accessible departments.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can export
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get accessible departments
    accessible_dept_ids = rbac.get_accessible_departments(user)
    
    # Filter by RBAC
    if accessible_dept_ids is not None:  # Not Admin
        if request.department_ids:
            # Check if requested departments are accessible
            if not all(d in accessible_dept_ids for d in request.department_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access some departments"
                )
            dept_ids = request.department_ids
        else:
            dept_ids = accessible_dept_ids
    else:
        dept_ids = request.department_ids
    
    # Generate report
    service = ExcelService(db)
    excel_file = service.generate_department_report(
        date_from=request.date_from,
        date_to=request.date_to,
        department_ids=dept_ids,
        late_only=request.late_only,
        include_comments=request.include_comments
    )
    
    filename = f"department_report_{request.date_from}_{request.date_to}.xlsx"
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/employee/{employee_id}")
async def export_employee_report(
    employee_id: int,
    request: ExcelExportRequest,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Export employee report to Excel.
    ROP and Admin can export.
    ROP can only export employees from accessible departments.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can export
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if user can view this employee
    from app.models.user import User
    target_user = db.query(User).filter(User.id == employee_id).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    if not rbac.can_view_employee(user, target_user.department_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access this employee"
        )
    
    # Generate report
    service = ExcelService(db)
    excel_file = service.generate_employee_report(
        user_id=employee_id,
        date_from=request.date_from,
        date_to=request.date_to,
        include_comments=request.include_comments
    )
    
    filename = f"employee_{target_user.name}_{request.date_from}_{request.date_to}.xlsx"
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/late-arrivals")
async def export_late_arrivals_report(
    request: ExcelExportRequest,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Export late arrivals report to Excel.
    Only ROP and Admin can export.
    ROP can only export their accessible departments.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can export
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get accessible departments
    accessible_dept_ids = rbac.get_accessible_departments(user)
    
    # Filter by RBAC
    if accessible_dept_ids is not None:  # Not Admin
        if request.department_ids:
            if not all(d in accessible_dept_ids for d in request.department_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot access some departments"
                )
            dept_ids = request.department_ids
        else:
            dept_ids = accessible_dept_ids
    else:
        dept_ids = request.department_ids
    
    # Generate report
    service = ExcelService(db)
    excel_file = service.generate_late_arrivals_report(
        date_from=request.date_from,
        date_to=request.date_to,
        department_ids=dept_ids
    )
    
    filename = f"late_arrivals_{request.date_from}_{request.date_to}.xlsx"
    
    return StreamingResponse(
        excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
