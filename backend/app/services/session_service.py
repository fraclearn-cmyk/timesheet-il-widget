"""
Service layer for work session management
Separates business logic from API endpoints
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.work_session import WorkSession
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class SessionService:
    """Business logic for work sessions with proper error handling"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_current_session(
        self, 
        account_id: str, 
        user_id: int
    ) -> Optional[WorkSession]:
        """
        Get active or paused session for user
        
        Args:
            account_id: Account ID (validated)
            user_id: User ID (validated)
            
        Returns:
            WorkSession or None
        """
        try:
            session = self.db.query(WorkSession).filter(
                and_(
                    WorkSession.account_id == account_id,
                    WorkSession.user_id == user_id,
                    WorkSession.status.in_(['active', 'paused'])
                )
            ).first()
            return session
        except Exception as e:
            logger.error(f"Error getting current session: {e}")
            return None
    
    def create_session(
        self, 
        account_id: str, 
        user_id: int,
        user_name: str
    ) -> WorkSession:
        """
        Create new work session with validation
        
        Args:
            account_id: Account ID (must be alphanumeric)
            user_id: User ID (must be positive)
            user_name: User name (sanitized)
            
        Returns:
            Created WorkSession
            
        Raises:
            ValueError: If validation fails or active session exists
        """
        try:
            # Validate inputs
            if not account_id or not isinstance(account_id, str):
                raise ValueError("Invalid account_id")
            if not user_id or user_id <= 0:
                raise ValueError("Invalid user_id")
            
            # Check for existing active session
            existing = self.get_current_session(account_id, user_id)
            if existing:
                raise ValueError(f"Active session already exists: {existing.session_id}")
            
            # Sanitize user_name (remove HTML tags)
            import re
            clean_name = re.sub(r'<[^>]+>', '', user_name) if user_name else 'Unknown'
            
            # Create new session
            session = WorkSession(
                account_id=account_id,
                user_id=user_id,
                user_name=clean_name[:100],  # Limit length
                start_time=datetime.utcnow(),
                status='active'
            )
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"Session created: {session.session_id} for user {user_id}")
            return session
            
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating session: {e}")
            raise ValueError(f"Failed to create session: {str(e)}")
    
    def update_session(
        self, 
        session_id: int,
        status: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Optional[WorkSession]:
        """
        Update existing session with validation
        
        Args:
            session_id: Session ID
            status: New status (active, paused, finished)
            comment: Optional comment (sanitized)
            
        Returns:
            Updated WorkSession or None if not found
            
        Raises:
            ValueError: If validation fails
        """
        try:
            session = self.db.query(WorkSession).filter(
                WorkSession.session_id == session_id
            ).first()
            
            if not session:
                logger.warning(f"Session not found: {session_id}")
                return None
            
            # Validate and update status
            if status:
                valid_statuses = ['active', 'paused', 'finished']
                if status not in valid_statuses:
                    raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
                session.status = status
                
                if status == 'finished':
                    session.end_time = datetime.utcnow()
            
            # Sanitize and update comment
            if comment:
                import re
                clean_comment = re.sub(r'<[^>]+>', '', comment)
                session.comment = clean_comment[:500]  # Limit length
            
            self.db.commit()
            self.db.refresh(session)
            
            logger.info(f"Session updated: {session_id} -> status={status}")
            return session
            
        except ValueError:
            raise
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating session {session_id}: {e}")
            raise ValueError(f"Failed to update session: {str(e)}")
    
    def finish_session(self, session_id: int) -> Optional[WorkSession]:
        """
        Finish work session
        
        Args:
            session_id: Session ID
            
        Returns:
            Finished session or None
        """
        return self.update_session(session_id, status='finished')
    
    def get_user_sessions(
        self,
        account_id: str,
        user_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[WorkSession]:
        """
        Get user's sessions with pagination
        
        Args:
            account_id: Account ID
            user_id: User ID
            limit: Max results (default 100, max 1000)
            offset: Offset for pagination
            
        Returns:
            List of sessions
        """
        try:
            # Validate pagination params
            limit = min(max(1, limit), 1000)  # Between 1 and 1000
            offset = max(0, offset)
            
            sessions = self.db.query(WorkSession).filter(
                and_(
                    WorkSession.account_id == account_id,
                    WorkSession.user_id == user_id
                )
            ).order_by(
                WorkSession.start_time.desc()
            ).limit(limit).offset(offset).all()
            
            return sessions
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return []
