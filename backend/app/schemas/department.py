"""Department schemas"""
from pydantic import BaseModel, Field
from datetime import time, datetime
from typing import Optional


class DepartmentBase(BaseModel):
    """Base department schema"""
    name: str = Field(..., min_length=1, max_length=255)
    work_start_time: time = Field(..., description="Work start time, e.g. 09:00:00")
    work_end_time: time = Field(..., description="Work end time, e.g. 18:00:00")


class DepartmentCreate(DepartmentBase):
    """Schema for creating department"""
    pass


class DepartmentUpdate(BaseModel):
    """Schema for updating department schedule"""
    work_start_time: Optional[time] = None
    work_end_time: Optional[time] = None
    is_active: Optional[bool] = None


class DepartmentResponse(DepartmentBase):
    """Department response schema"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DepartmentScheduleResponse(BaseModel):
    """Department schedule response"""
    department_id: int
    department_name: str
    work_start_time: time
    work_end_time: time
    
    class Config:
        from_attributes = True
