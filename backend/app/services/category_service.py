from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.activity_category import ActivityCategory
from app.schemas.activity_category import ActivityCategoryCreate, ActivityCategoryUpdate


class CategoryService:
    """Service for managing activity categories"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_category(self, account_id: str, data: ActivityCategoryCreate) -> ActivityCategory:
        """Create new activity category"""
        category = ActivityCategory(
            account_id=account_id,
            name=data.name,
            color=data.color,
            icon=data.icon,
            is_active=data.is_active if data.is_active is not None else True
        )
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category
    
    def get_categories(self, account_id: str, active_only: bool = False) -> List[ActivityCategory]:
        """Get all categories for account"""
        query = self.db.query(ActivityCategory)\
            .filter(ActivityCategory.account_id == account_id)
        
        if active_only:
            query = query.filter(ActivityCategory.is_active == True)
        
        return query.order_by(ActivityCategory.name).all()
    
    def get_category(self, category_id: int) -> Optional[ActivityCategory]:
        """Get category by ID"""
        return self.db.query(ActivityCategory)\
            .filter(ActivityCategory.id == category_id)\
            .first()
    
    def update_category(self, category_id: int, data: ActivityCategoryUpdate) -> ActivityCategory:
        """Update category"""
        category = self.get_category(category_id)
        if not category:
            raise ValueError("Category not found")
        
        if data.name is not None:
            category.name = data.name
        if data.color is not None:
            category.color = data.color
        if data.icon is not None:
            category.icon = data.icon
        if data.is_active is not None:
            category.is_active = data.is_active
        
        self.db.commit()
        self.db.refresh(category)
        return category
    
    def delete_category(self, category_id: int) -> bool:
        """Delete category (soft delete by setting is_active=False)"""
        category = self.get_category(category_id)
        if not category:
            raise ValueError("Category not found")
        
        category.is_active = False
        self.db.commit()
        return True
