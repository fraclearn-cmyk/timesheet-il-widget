from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.v1.dependencies import APIProblem, RequestContext, get_request_context
from app.services.category_service import CategoryService
from app.schemas.activity_category import (
    ActivityCategoryCreate,
    ActivityCategoryUpdate,
    ActivityCategoryResponse,
)
from sqlalchemy.exc import IntegrityError

router = APIRouter()


@router.post("", response_model=ActivityCategoryResponse, status_code=201)
def create_category(
    account_id: str,
    data: ActivityCategoryCreate,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Create new activity category"""
    service = CategoryService(db)
    try:
        category = service.create_category(str(context.account_id), data)
    except IntegrityError as error:
        raise APIProblem(409, "CONFLICT", "Category already exists.") from error
    return ActivityCategoryResponse.from_orm(category)


@router.get("", response_model=List[ActivityCategoryResponse])
def get_categories(
    account_id: str,
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Get all categories for account"""
    service = CategoryService(db)
    categories = service.get_categories(str(context.account_id), active_only)
    return [ActivityCategoryResponse.from_orm(c) for c in categories]


@router.get("/{category_id}", response_model=ActivityCategoryResponse)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Get category by ID"""
    service = CategoryService(db)
    category = service.get_category(category_id, context.account_id)

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    return ActivityCategoryResponse.from_orm(category)


@router.put("/{category_id}", response_model=ActivityCategoryResponse)
def update_category(
    category_id: int,
    data: ActivityCategoryUpdate,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Update category"""
    service = CategoryService(db)
    try:
        category = service.update_category(category_id, data, context.account_id)
        return ActivityCategoryResponse.from_orm(category)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
):
    """Delete category (soft delete)"""
    service = CategoryService(db)
    try:
        service.delete_category(category_id, context.account_id)
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
