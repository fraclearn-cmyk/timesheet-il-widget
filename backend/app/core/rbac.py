"""Role-Based Access Control (RBAC) system"""
from typing import List, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.rop_permission import RopPermission


class RBACService:
    """Service for Role-Based Access Control"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_by_amocrm_id(self, amocrm_user_id: int, amocrm_account_id: int) -> Optional[User]:
        """Get user by amoCRM ID"""
        return self.db.query(User).filter(
            User.amocrm_user_id == amocrm_user_id,
            User.amocrm_account_id == amocrm_account_id,
            User.is_active == True
        ).first()
    
    def get_or_create_user(
        self, 
        amocrm_user_id: int, 
        amocrm_account_id: int, 
        name: str, 
        email: Optional[str] = None
    ) -> User:
        """Get existing user or create new one with EMPLOYEE role"""
        user = self.get_user_by_amocrm_id(amocrm_user_id, amocrm_account_id)
        
        if not user:
            user = User(
                amocrm_user_id=amocrm_user_id,
                amocrm_account_id=amocrm_account_id,
                name=name,
                email=email,
                role=UserRole.EMPLOYEE
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        
        return user
    
    def get_user_role(self, amocrm_user_id: int, amocrm_account_id: int) -> Optional[UserRole]:
        """Get user role"""
        user = self.get_user_by_amocrm_id(amocrm_user_id, amocrm_account_id)
        return user.role if user else None
    
    def is_admin(self, user: User) -> bool:
        """Check if user is admin"""
        return user.role == UserRole.ADMIN
    
    def is_rop(self, user: User) -> bool:
        """Check if user is ROP"""
        return user.role == UserRole.ROP
    
    def is_employee(self, user: User) -> bool:
        """Check if user is employee"""
        return user.role == UserRole.EMPLOYEE
    
    def get_rop_departments(self, user_id: int) -> List[int]:
        """Get list of department IDs that ROP can manage"""
        permissions = self.db.query(RopPermission).filter(
            RopPermission.user_id == user_id
        ).all()
        return [p.department_id for p in permissions]
    
    def can_view_department(self, user: User, department_id: int) -> bool:
        """Check if user can view department data"""
        # Admin can view all departments
        if self.is_admin(user):
            return True
        
        # ROP can only view allowed departments
        if self.is_rop(user):
            allowed_departments = self.get_rop_departments(user.id)
            return department_id in allowed_departments
        
        # Employees cannot view department data
        return False
    
    def can_view_employee(self, user: User, employee_department_id: Optional[int]) -> bool:
        """Check if user can view employee data"""
        # Admin can view all employees
        if self.is_admin(user):
            return True
        
        # ROP can only view employees from allowed departments
        if self.is_rop(user) and employee_department_id:
            allowed_departments = self.get_rop_departments(user.id)
            return employee_department_id in allowed_departments
        
        # Employees can only view their own data
        return False
    
    def can_force_finish(self, user: User) -> bool:
        """Check if user can force finish work sessions"""
        # Only admin can force finish
        return self.is_admin(user)
    
    def can_add_comment(self, user: User) -> bool:
        """Check if user can add comments to work sessions"""
        # ROP and Admin can add comments
        return self.is_rop(user) or self.is_admin(user)
    
    def can_export_excel(self, user: User) -> bool:
        """Check if user can export Excel reports"""
        # ROP and Admin can export
        return self.is_rop(user) or self.is_admin(user)
    
    def can_manage_departments(self, user: User) -> bool:
        """Check if user can manage departments (schedules, etc)"""
        # Only admin can manage departments
        return self.is_admin(user)
    
    def can_restart_session(self, user: User) -> bool:
        """Check if user can restart work session on the same day"""
        return user.allow_restart_session
    
    def get_accessible_departments(self, user: User) -> Optional[List[int]]:
        """
        Get list of department IDs accessible to user.
        Returns None for Admin (can access all), list of IDs for ROP, empty list for Employee
        """
        if self.is_admin(user):
            return None  # None means "all departments"
        
        if self.is_rop(user):
            return self.get_rop_departments(user.id)
        
        return []  # Employee has no access to departments


# Dependency for FastAPI
def get_rbac_service(db: Session = Depends(get_db)) -> RBACService:
    """FastAPI dependency to get RBAC service"""
    return RBACService(db)


def require_admin(
    amocrm_user_id: int,
    amocrm_account_id: int,
    rbac: RBACService = Depends(get_rbac_service)
) -> User:
    """Require admin role"""
    user = rbac.get_user_by_amocrm_id(amocrm_user_id, amocrm_account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not rbac.is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    return user


def require_rop_or_admin(
    amocrm_user_id: int,
    amocrm_account_id: int,
    rbac: RBACService = Depends(get_rbac_service)
) -> User:
    """Require ROP or Admin role"""
    user = rbac.get_user_by_amocrm_id(amocrm_user_id, amocrm_account_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if not (rbac.is_rop(user) or rbac.is_admin(user)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ROP or Admin role required"
        )
    
    return user
