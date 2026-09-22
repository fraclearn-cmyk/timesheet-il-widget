"""KPI calculation service"""

from sqlalchemy.orm import Session
from sqlalchemy import tuple_
from datetime import datetime, timedelta, date, time
from typing import Dict

from app.models.work_session import WorkSession
from app.models.user import User
from app.models.group_member import GroupMember
from app.models.widget_group import WidgetGroup
from app.schemas.kpi import KPIMetrics, ChartData
from app.core.business_time import business_date, local_period_utc_bounds
from app.core.time_utils import utc_now


class KPIService:
    """Service for calculating KPI metrics"""

    def __init__(self, db: Session):
        self.db = db

    def _calendar_for(self, user: User | None) -> tuple[str, time, time]:
        """Return a user's active group calendar, or the explicit UTC legacy one."""
        if user is None:
            return "UTC", time(9), time(18)
        group = (
            self.db.query(WidgetGroup)
            .join(
                GroupMember,
                (GroupMember.group_id == WidgetGroup.id)
                & (GroupMember.account_id == WidgetGroup.account_id),
            )
            .filter(
                GroupMember.account_id == user.amocrm_account_id,
                GroupMember.user_id == user.id,
                GroupMember.is_active.is_(True),
                WidgetGroup.is_active.is_(True),
            )
            .one_or_none()
        )
        if group is None:
            return "UTC", time(9), time(18)
        return group.timezone, group.work_start_time, group.work_end_time

    def _period_days(self, user: User, now: datetime) -> tuple[date, date, date]:
        zone, start, end = self._calendar_for(user)
        day = business_date(now, zone, start, end)
        return day, day - timedelta(days=day.weekday()), day.replace(day=1)

    def _sessions_for_business_days(
        self, user: User, first_day: date, end_day: date
    ) -> list[WorkSession]:
        """Return sessions whose group workday is in [first_day, end_day)."""
        zone, start, end = self._calendar_for(user)
        first_utc, _ = local_period_utc_bounds(first_day, zone)
        # A night shift's session may begin after local midnight but still
        # belong to the preceding business day, so fetch one local day beyond
        # the target range and classify it below.
        end_utc, _ = local_period_utc_bounds(end_day + timedelta(days=1), zone)
        sessions = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.amocrm_user_id == user.amocrm_user_id,
                WorkSession.amocrm_account_id == user.amocrm_account_id,
                WorkSession.start_time >= first_utc,
                WorkSession.start_time < end_utc,
            )
            .all()
        )
        return [
            session
            for session in sessions
            if first_day <= business_date(session.start_time, zone, start, end) < end_day
        ]

    def calculate_user_kpi(self, user_id: int, amocrm_user_id: str) -> KPIMetrics:
        """Calculate KPI for a user"""
        now = utc_now()
        user = self.db.get(User, user_id)
        if user is None or user.amocrm_user_id != int(amocrm_user_id):
            raise ValueError("Mismatched user identity")

        calendar_day, week_start_day, month_start_day = self._period_days(user, now)

        # Today hours
        today_sessions = self._sessions_for_business_days(
            user, calendar_day, calendar_day + timedelta(days=1)
        )
        hours_today = sum(s.total_work_time for s in today_sessions) / 3600

        # Week hours
        week_sessions = self._sessions_for_business_days(
            user, week_start_day, calendar_day + timedelta(days=1)
        )
        hours_week = sum(s.total_work_time for s in week_sessions) / 3600

        # Month hours
        month_sessions = self._sessions_for_business_days(
            user, month_start_day, calendar_day + timedelta(days=1)
        )
        hours_month = sum(s.total_work_time for s in month_sessions) / 3600

        # Average per day (month)
        days_in_month = calendar_day.day
        avg_hours = hours_month / days_in_month if days_in_month > 0 else 0

        # Late counts
        late_week = sum(1 for s in week_sessions if s.is_late)
        late_month = sum(1 for s in month_sessions if s.is_late)

        # Completion % (assuming 8h norm)
        completion = (avg_hours / 8) * 100 if avg_hours > 0 else 0

        # Current status
        current_session = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.amocrm_user_id == amocrm_user_id,
                WorkSession.amocrm_account_id == user.amocrm_account_id,
                WorkSession.end_time.is_(None),
            )
            .first()
        )

        if current_session:
            status = current_session.current_status.value
            # Legacy online hint only; session updates are not confirmed CRM work.
            is_online = (
                (now - current_session.updated_at).total_seconds() < 300
                if current_session.updated_at
                else False
            )
        else:
            status = "offline"
            is_online = False

        return KPIMetrics(
            hours_today=round(hours_today, 2),
            hours_week=round(hours_week, 2),
            hours_month=round(hours_month, 2),
            avg_hours_per_day=round(avg_hours, 2),
            late_count_week=late_week,
            late_count_month=late_month,
            completion_percentage=round(completion, 1),
            current_status=status,
            is_online=is_online,
        )

    def calculate_department_kpi(
        self,
        department_id: int,
        *,
        account_id: int | None = None,
        visible_internal_user_ids: set[int] | None = None,
    ) -> KPIMetrics:
        """Calculate KPI for a department"""
        now = utc_now()

        # Get all users in department
        user_query = self.db.query(User).filter(User.department_id == department_id)
        if account_id is not None:
            user_query = user_query.filter(User.amocrm_account_id == account_id)
        if visible_internal_user_ids is not None:
            user_query = user_query.filter(User.id.in_(visible_internal_user_ids))
        users = user_query.all()
        user_ids = [(u.amocrm_account_id, u.amocrm_user_id) for u in users]

        if not user_ids:
            return KPIMetrics(
                hours_today=0,
                hours_week=0,
                hours_month=0,
                avg_hours_per_day=0,
                late_count_week=0,
                late_count_month=0,
                completion_percentage=0,
                current_status="offline",
                is_online=False,
                total_employees=0,
                online_now=0,
            )

        # Each employee's periods are defined by that employee's active group.
        today_sessions = []
        week_sessions = []
        month_sessions = []
        calendar_days = []
        for user in users:
            calendar_day, week_start_day, month_start_day = self._period_days(user, now)
            today_sessions.extend(
                self._sessions_for_business_days(
                    user, calendar_day, calendar_day + timedelta(days=1)
                )
            )
            week_sessions.extend(
                self._sessions_for_business_days(
                    user, week_start_day, calendar_day + timedelta(days=1)
                )
            )
            month_sessions.extend(
                self._sessions_for_business_days(
                    user, month_start_day, calendar_day + timedelta(days=1)
                )
            )
            calendar_days.append(calendar_day.day)

        hours_today = sum(s.total_work_time for s in today_sessions) / 3600
        hours_week = sum(s.total_work_time for s in week_sessions) / 3600
        hours_month = sum(s.total_work_time for s in month_sessions) / 3600

        employee_days = sum(calendar_days)
        avg_hours = hours_month / employee_days if employee_days else 0

        late_week = sum(1 for s in week_sessions if s.is_late)
        late_month = sum(1 for s in month_sessions if s.is_late)

        completion = (avg_hours / 8) * 100 if avg_hours > 0 else 0

        # Online count
        online = (
            self.db.query(WorkSession)
            .filter(
                tuple_(WorkSession.amocrm_account_id, WorkSession.amocrm_user_id).in_(
                    user_ids
                ),
                WorkSession.end_time.is_(None),
                WorkSession.updated_at >= now - timedelta(minutes=5),
            )
            .count()
        )

        return KPIMetrics(
            hours_today=round(hours_today / len(users) if users else 0, 2),
            hours_week=round(hours_week / len(users) if users else 0, 2),
            hours_month=round(hours_month / len(users) if users else 0, 2),
            avg_hours_per_day=round(avg_hours, 2),
            late_count_week=late_week,
            late_count_month=late_month,
            completion_percentage=round(completion, 1),
            current_status="department",
            is_online=online > 0,
            total_employees=len(users),
            online_now=online,
        )

    def get_chart_data(
        self, user_id: str, days: int = 7, *, account_id=None
    ) -> ChartData:
        """Get chart data for user (last N days)"""
        if account_id is None:
            from app.services.session_service import SessionService

            account_id = SessionService(self.db)._legacy_user(user_id).amocrm_account_id
        user = (
            self.db.query(User)
            .filter(
                User.amocrm_user_id == int(user_id),
                User.amocrm_account_id == account_id,
            )
            .one_or_none()
        )
        zone, start, end = self._calendar_for(user)
        end_date = business_date(utc_now(), zone, start, end)
        start_date = end_date - timedelta(days=days - 1)

        first_utc, _ = local_period_utc_bounds(start_date, zone)
        end_utc, _ = local_period_utc_bounds(end_date + timedelta(days=2), zone)
        sessions = (
            self.db.query(WorkSession)
            .filter(
                WorkSession.amocrm_user_id == user_id,
                WorkSession.amocrm_account_id == account_id,
                WorkSession.start_time >= first_utc,
                WorkSession.start_time < end_utc,
            )
            .all()
        )

        data_by_date: Dict[date, float] = {}
        for session in sessions:
            session_date = business_date(session.start_time, zone, start, end)
            if not start_date <= session_date <= end_date:
                continue
            hours = session.total_work_time / 3600
            data_by_date[session_date] = data_by_date.get(session_date, 0) + hours

        # Generate all dates in range
        labels = []
        values = []
        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime("%Y-%m-%d"))
            values.append(round(data_by_date.get(current_date, 0), 2))
            current_date += timedelta(days=1)

        # Chart.js format
        datasets = [
            {
                "label": "Рабочие часы",
                "data": values,
                "borderColor": "rgb(75, 192, 192)",
                "backgroundColor": "rgba(75, 192, 192, 0.2)",
                "tension": 0.1,
            }
        ]

        return ChartData(labels=labels, datasets=datasets)

    def get_department_chart_data(
        self,
        department_id: int,
        days: int = 7,
        *,
        account_id: int | None = None,
        visible_internal_user_ids: set[int] | None = None,
    ) -> ChartData:
        """Get chart data for department"""
        now = utc_now()

        # Get users
        user_query = self.db.query(User).filter(User.department_id == department_id)
        if account_id is not None:
            user_query = user_query.filter(User.amocrm_account_id == account_id)
        if visible_internal_user_ids is not None:
            user_query = user_query.filter(User.id.in_(visible_internal_user_ids))
        users = user_query.all()
        user_ids = [(u.amocrm_account_id, u.amocrm_user_id) for u in users]

        if not user_ids:
            return ChartData(labels=[], datasets=[])

        end_date = max(self._period_days(user, now)[0] for user in users)
        start_date = end_date - timedelta(days=days - 1)
        data_by_date: Dict[date, float] = {}
        for user in users:
            sessions = self._sessions_for_business_days(
                user, start_date, end_date + timedelta(days=1)
            )
            zone, start, end = self._calendar_for(user)
            for session in sessions:
                session_date = business_date(session.start_time, zone, start, end)
                hours = session.total_work_time / 3600
                data_by_date[session_date] = data_by_date.get(session_date, 0) + hours

        # Generate labels and values
        labels = []
        values = []
        current_date = start_date
        while current_date <= end_date:
            labels.append(current_date.strftime("%Y-%m-%d"))
            avg = data_by_date.get(current_date, 0) / len(users) if users else 0
            values.append(round(avg, 2))
            current_date += timedelta(days=1)

        datasets = [
            {
                "label": "Средние часы",
                "data": values,
                "borderColor": "rgb(54, 162, 235)",
                "backgroundColor": "rgba(54, 162, 235, 0.2)",
                "tension": 0.1,
            }
        ]

        return ChartData(labels=labels, datasets=datasets)
