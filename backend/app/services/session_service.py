"""Legacy adapter: external IDs are resolved to account-scoped model identity.

Resolution is not authorization; OAuth/RBAC belongs to phase 2.
"""

from app.core.time_utils import utc_now
import re

from sqlalchemy.orm import Session
from app.models import User, WorkSession, WorkStatus, StatusTransition


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def _user(self, account_id, amocrm_user_id):
        try:
            account_id = int(account_id)
            amocrm_user_id = int(amocrm_user_id)
        except (TypeError, ValueError):
            raise ValueError("Invalid external account/user identity") from None
        user = (
            self.db.query(User)
            .filter(
                User.amocrm_account_id == account_id,
                User.amocrm_user_id == amocrm_user_id,
            )
            .one_or_none()
        )
        if user is None:
            raise ValueError("Unknown account-scoped amoCRM user")
        return user

    def _legacy_user(self, amocrm_user_id):
        """Deprecated routes lack account context: fail closed on ambiguity."""
        users = self.db.query(User).filter(User.amocrm_user_id == amocrm_user_id).all()
        if len(users) != 1:
            raise ValueError(
                "Unknown or ambiguous external user; account context required"
            )
        return users[0]

    def get_current_session(self, account_id, user_id=None):
        if user_id is None:
            user = self._legacy_user(account_id)
            account_id, user_id = user.amocrm_account_id, user.amocrm_user_id
        user = self._user(account_id, user_id)
        return (
            self.db.query(WorkSession)
            .filter(
                WorkSession.amocrm_account_id == user.amocrm_account_id,
                WorkSession.amocrm_user_id == user.amocrm_user_id,
                WorkSession.current_status.in_([WorkStatus.WORKING, WorkStatus.BREAK]),
            )
            .first()
        )

    def create_session(self, account_id, user_id, user_name):
        user = self._user(account_id, user_id)
        if self.get_current_session(account_id, user_id):
            raise ValueError("Active session already exists")
        now = utc_now()
        work = WorkSession(
            amocrm_account_id=user.amocrm_account_id,
            amocrm_user_id=user.amocrm_user_id,
            user_name=re.sub(r"<[^>]+>", "", user_name or user.name)[:255],
            start_time=now,
            current_status=WorkStatus.WORKING,
        )
        work.status_transitions.append(
            StatusTransition(to_status="working", timestamp=now)
        )
        self.db.add(work)
        self.db.commit()
        self.db.refresh(work)
        return work

    def update_session(self, session_id, status=None, comment=None):
        work = self.db.get(WorkSession, session_id)
        if work is None:
            return None
        if comment is not None:
            raise ValueError("Comments require a WorkComment with an attributed author")
        if status is not None:
            status = {"active": "working", "paused": "break"}.get(status, status)
            try:
                target = WorkStatus(status)
            except ValueError:
                raise ValueError("Invalid work status") from None
            if (
                work.current_status == WorkStatus.FINISHED
                and target != WorkStatus.FINISHED
            ):
                raise ValueError("Finished session cannot be reopened")
            if work.current_status != target:
                now = utc_now()
                work.status_transitions.append(
                    StatusTransition(
                        from_status=work.current_status.value,
                        to_status=target.value,
                        timestamp=now,
                    )
                )
                work.current_status = target
                if target == WorkStatus.FINISHED:
                    work.end_time = now
        self.db.commit()
        self.db.refresh(work)
        return work

    def finish_session(self, session_id):
        return self.update_session(session_id, status=WorkStatus.FINISHED)

    def get_user_sessions(self, account_id, user_id, limit=100, offset=0):
        user = self._user(account_id, user_id)
        return (
            self.db.query(WorkSession)
            .filter(
                WorkSession.amocrm_account_id == user.amocrm_account_id,
                WorkSession.amocrm_user_id == user.amocrm_user_id,
            )
            .order_by(WorkSession.start_time.desc())
            .limit(min(max(1, limit), 1000))
            .offset(max(0, offset))
            .all()
        )

    def get_session_by_id(self, session_id):
        return self.db.get(WorkSession, session_id)

    def start_session(self, data, *, account_id):
        user = self._user(account_id, data.user_id)
        return self.create_session(
            user.amocrm_account_id, user.amocrm_user_id, data.user_name
        )

    def _change_current(self, account_id, amocrm_user_id, status):
        work = self.get_current_session(account_id, amocrm_user_id)
        if work is None:
            raise ValueError("No current session")
        return self.update_session(work.id, status=status)

    def take_break(self, account_id, amocrm_user_id):
        return self._change_current(account_id, amocrm_user_id, WorkStatus.BREAK)

    def resume_work(self, account_id, amocrm_user_id):
        return self._change_current(account_id, amocrm_user_id, WorkStatus.WORKING)

    def finish_work(self, account_id, amocrm_user_id):
        return self._change_current(account_id, amocrm_user_id, WorkStatus.FINISHED)

    def get_session_history(
        self,
        amocrm_user_id,
        date_from=None,
        date_to=None,
        limit=100,
        *,
        account_id=None
    ):
        user = (
            self._legacy_user(amocrm_user_id)
            if account_id is None
            else self._user(account_id, amocrm_user_id)
        )
        query = self.db.query(WorkSession).filter(
            WorkSession.amocrm_account_id == user.amocrm_account_id,
            WorkSession.amocrm_user_id == user.amocrm_user_id,
        )
        if date_from is not None:
            query = query.filter(WorkSession.start_time >= date_from)
        if date_to is not None:
            query = query.filter(WorkSession.start_time <= date_to)
        return (
            query.order_by(WorkSession.start_time.desc())
            .limit(min(max(1, limit), 1000))
            .all()
        )
