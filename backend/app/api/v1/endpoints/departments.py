"""Department endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.rbac import RBACService, get_rbac_service
from app.models.department import Department
from app.schemas.department import (
    DepartmentResponse,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentScheduleResponse
)

router = APIRouter()


@router.get("/", response_model=List[DepartmentResponse])
def get_departments(
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get list of departments.
    - Admin: all departments
    - ROP: only allowed departments
    - Employee: forbidden
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Only ROP and Admin can view departments
    if rbac.is_employee(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Get accessible departments
    accessible_dept_ids = rbac.get_accessible_departments(user)
    
    # Admin (None) - get all departments
    if accessible_dept_ids is None:
        departments = db.query(Department).filter(
            Department.is_active == True
        ).all()
    # ROP - get only allowed departments
    elif accessible_dept_ids:
        departments = db.query(Department).filter(
            Department.id.in_(accessible_dept_ids),
            Department.is_active == True
        ).all()
    else:
        departments = []
    
    return departments


@router.get("/{department_id}/schedule", response_model=DepartmentScheduleResponse)
def get_department_schedule(
    department_id: int,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Get department schedule.
    Used by widget to check if employee is late.
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        # If user not found, create with EMPLOYEE role
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    department = db.query(Department).filter(
        Department.id == department_id,
        Department.is_active == True
    ).first()
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    return DepartmentScheduleResponse(
        department_id=department.id,
        department_name=department.name,
        work_start_time=department.work_start_time,
        work_end_time=department.work_end_time
    )


@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    department_data: DepartmentCreate,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Create new department (Admin only).
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not rbac.can_manage_departments(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    # Check if department with this name already exists
    existing = db.query(Department).filter(
        Department.name == department_data.name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department with this name already exists"
        )
    
    department = Department(**department_data.dict())
    db.add(department)
    db.commit()
    db.refresh(department)
    
    return department


@router.put("/{department_id}/schedule", response_model=DepartmentResponse)
def update_department_schedule(
    department_id: int,
    update_data: DepartmentUpdate,
    user_id: int = Header(..., alias="X-User-Id"),
    account_id: int = Header(..., alias="X-Account-Id"),
    db: Session = Depends(get_db),
    rbac: RBACService = Depends(get_rbac_service)
):
    """
    Update department schedule (Admin only).
    """
    user = rbac.get_user_by_amocrm_id(user_id, account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not rbac.can_manage_departments(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    department = db.query(Department).filter(
        Department.id == department_id
    ).first()
    
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    
    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(department, field, value)
    
    db.commit()
    db.refresh(department)
    
    return department
