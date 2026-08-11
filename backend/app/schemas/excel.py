"""Excel export schemas"""
from pydantic import BaseModel
from datetime import date
from typing import Optional, List


class ExcelExportRequest(BaseModel):
    """Request for Excel export"""
    date_from: date
    date_to: date
    department_ids: Optional[List[int]] = None  # None = all accessible
    user_ids: Optional[List[int]] = None  # None = all
    late_only: bool = False
    include_comments: bool = True


class ExcelExportResponse(BaseModel):
    """Response with Excel file"""
    filename: str
    content_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    # File будет возвращен через StreamingResponse
