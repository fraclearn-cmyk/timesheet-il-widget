from pydantic import BaseModel
from typing import Optional


class ActivityCategoryBase(BaseModel):
    """Base activity category schema"""
    name: str
    display_name: str
    color: str
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0


class ActivityCategoryCreate(ActivityCategoryBase):
    """Schema for creating activity category"""
    is_active: bool = True


class ActivityCategoryUpdate(BaseModel):
    """Schema for updating activity category"""
    display_name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ActivityCategoryResponse(ActivityCategoryBase):
    """Schema for activity category response"""
    id: int
    is_active: bool

    class Config:
        from_attributes = True
