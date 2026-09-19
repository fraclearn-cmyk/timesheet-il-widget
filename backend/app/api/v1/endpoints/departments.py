"""Department endpoints"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.dependencies import (
    RequestContext,
    get_request_context,
    require_visible_department,
)
from app.core.access_policy import AccessPolicy
from app.models.department import Department
from app.schemas.department import (
    DepartmentResponse,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentScheduleResponse,
)

router = APIRouter()


@router.get("/", response_model=List[DepartmentResponse])
def get_departments(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get list of departments.
    - Admin: all departments
    - ROP: only allowed departments
    - Employee: forbidden
    """
    user = context.user

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    policy = AccessPolicy(db, context)
    if not (policy.is_admin() or policy.is_manager()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    # Get accessible departments
    accessible_dept_ids = policy.accessible_department_ids()

    scoped_departments = db.query(Department).filter(
        Department.account_id == context.account_id,
        Department.is_active.is_(True),
    )

    # Admin (None) - get all departments in the verified account
    if accessible_dept_ids is None:
        departments = scoped_departments.distinct().all()
    # ROP - get only allowed departments
    elif accessible_dept_ids:
        departments = (
            scoped_departments.filter(Department.id.in_(accessible_dept_ids))
            .distinct()
            .all()
        )
    else:
        departments = []

    return departments


@router.get("/{department_id}/schedule", response_model=DepartmentScheduleResponse)
def get_department_schedule(
    department_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """
    Get department schedule.
    Used by widget to check if employee is late.
    """
    department = require_visible_department(db, context, department_id)

    return DepartmentScheduleResponse(
        department_id=department.id,
        department_name=department.name,
        work_start_time=department.work_start_time,
        work_end_time=department.work_end_time,
    )


@router.post(
    "/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED
)
def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """
    Create new department (Admin only).
    """
    if not AccessPolicy(db, context).can_manage_departments():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    # Check if department with this name already exists
    existing = (
        db.query(Department)
        .filter(
            Department.account_id == context.account_id,
            Department.name == department_data.name,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department with this name already exists",
        )

    department = Department(
        account_id=context.account_id, **department_data.model_dump()
    )
    db.add(department)
    db.commit()
    db.refresh(department)

    return department


@router.put("/{department_id}/schedule", response_model=DepartmentResponse)
def update_department_schedule(
    department_id: int,
    update_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """
    Update department schedule (Admin only).
    """
    if not AccessPolicy(db, context).can_manage_departments():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )

    department = (
        db.query(Department)
        .filter(
            Department.id == department_id,
            Department.account_id == context.account_id,
        )
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        )

    # Update fields
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(department, field, value)

    db.commit()
    db.refresh(department)

    return department
