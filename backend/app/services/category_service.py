from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.activity_category import ActivityCategory
from app.schemas.activity_category import ActivityCategoryCreate, ActivityCategoryUpdate


class CategoryService:
    """Service for managing activity categories"""

    def __init__(self, db: Session):
        self.db = db

    def create_category(
        self, account_id: str, data: ActivityCategoryCreate
    ) -> ActivityCategory:
        """Create new activity category"""
        category = ActivityCategory(
            account_id=int(account_id),
            name=data.name,
            display_name=data.display_name,
            color=data.color,
            icon=data.icon,
            description=data.description,
            is_active=data.is_active if data.is_active is not None else True,
            sort_order=data.sort_order,
        )
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def get_categories(
        self, account_id: str, active_only: bool = False
    ) -> List[ActivityCategory]:
        """Get all categories for account"""
        query = self.db.query(ActivityCategory).filter(
            ActivityCategory.account_id == int(account_id)
        )

        if active_only:
            query = query.filter(ActivityCategory.is_active.is_(True))

        return query.order_by(ActivityCategory.name).all()

    def get_category(
        self, category_id: int, account_id: Optional[int] = None
    ) -> Optional[ActivityCategory]:
        """Get category by ID"""
        query = self.db.query(ActivityCategory).filter(
            ActivityCategory.id == category_id
        )
        if account_id is not None:
            query = query.filter(ActivityCategory.account_id == int(account_id))
        return query.first()

    def update_category(
        self,
        category_id: int,
        data: ActivityCategoryUpdate,
        account_id: Optional[int] = None,
    ) -> ActivityCategory:
        """Update category"""
        category = self.get_category(category_id, account_id)
        if not category:
            raise ValueError("Category not found")

        if data.name is not None:
            category.name = data.name
        if data.display_name is not None:
            category.display_name = data.display_name
        if data.color is not None:
            category.color = data.color
        if data.icon is not None:
            category.icon = data.icon
        if data.is_active is not None:
            category.is_active = data.is_active
        if data.description is not None:
            category.description = data.description
        if data.sort_order is not None:
            category.sort_order = data.sort_order

        self.db.commit()
        self.db.refresh(category)
        return category

    def delete_category(
        self, category_id: int, account_id: Optional[int] = None
    ) -> bool:
        """Delete category (soft delete by setting is_active=False)"""
        category = self.get_category(category_id, account_id)
        if not category:
            raise ValueError("Category not found")

        category.is_active = False
        self.db.commit()
        return True
