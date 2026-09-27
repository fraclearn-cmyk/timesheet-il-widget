"""Derive privacy-safe activity intervals from persisted authoritative evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    ActivityInterval,
    CallEvent,
    CrmEvent,
    PresenceBatch,
    StatusTransition,
    User,
    WorkSession,
    WorkStatus,
)


class ActivityIntervalService:
    """Attach evidence only to the matching account/user WORKING segment."""

    _PRESENCE_GAP = timedelta(seconds=300)
    _PRESENCE_MAX_AGE = timedelta(minutes=10)

    def __init__(self, db: Session):
        self.db = db

    def attach_crm_event(self, event: CrmEvent) -> ActivityInterval | None:
        if not event.is_complete:
            return None
        user = self._verified_user(event)
        if user is None:
            return None
        self._lock_user(user)
        occurred_at = self._utc_naive(event.occurred_at)
        session = self._working_session(user, occurred_at, occurred_at)
        if session is None:
            return None
        interval = ActivityInterval.from_evidence(
            session,
            started_at=occurred_at,
            ended_at=occurred_at,
            source="crm_event",
            evidence=event,
        )
        self.db.add(interval)
        self.db.flush()
        self._recompute_durations(session)
        return interval

    def attach_call(self, event: CallEvent) -> ActivityInterval | None:
        if (
            not event.is_complete
            or event.direction not in {"incoming", "outgoing"}
            or event.duration_seconds is None
            or event.duration_seconds < 0
        ):
            return None
        user = self._verified_user(event)
        if user is None:
            return None
        self._lock_user(user)
        started_at = self._utc_naive(event.occurred_at)
        ended_at = started_at + timedelta(seconds=event.duration_seconds)
        session = self._working_session(user, started_at, ended_at)
        if session is None:
            return None
        interval = ActivityInterval.from_evidence(
            session,
            started_at=started_at,
            ended_at=ended_at,
            source="call",
            evidence=event,
        )
        self.db.add(interval)
        self.db.flush()
        self._recompute_durations(session)
        return interval

    def record_presence(
        self,
        *,
        account_id: int,
        user: User,
        command_id: UUID,
        window_started_at: datetime,
        last_seen_at: datetime,
        signal_count: int,
        received_at: datetime,
    ) -> ActivityInterval | None:
        if (
            not isinstance(command_id, UUID)
            or user.id is None
            or user.amocrm_account_id != account_id
        ):
            raise ValueError("invalid presence attribution")

        # Timesheet transitions take this same lock before changing status.
        # It also serializes UUID replay and interval merging across requests.
        self._lock_user(user)

        previous = self.db.scalar(
            select(PresenceBatch).where(
                PresenceBatch.account_id == account_id,
                PresenceBatch.user_id == user.id,
                PresenceBatch.command_id == command_id,
            )
        )
        if previous is not None:
            if (
                previous.window_started_at != window_started_at
                or previous.last_seen_at != last_seen_at
                or previous.signal_count != signal_count
            ):
                raise ValueError("presence command id was reused")
            return self._interval_for_batch(previous, user)

        self._validate_presence_times(
            window_started_at=window_started_at,
            last_seen_at=last_seen_at,
            received_at=received_at,
        )
        if not 1 <= signal_count <= 100_000:
            raise ValueError("invalid presence signal count")

        batch = PresenceBatch(
            account_id=account_id,
            user_id=user.id,
            command_id=command_id,
            window_started_at=window_started_at,
            last_seen_at=last_seen_at,
            signal_count=signal_count,
        )
        self.db.add(batch)
        self.db.flush()

        session = self._working_session(user, window_started_at, last_seen_at)
        if session is None:
            return None

        intervals = list(
            self.db.scalars(
                select(ActivityInterval)
                .where(
                    ActivityInterval.account_id == account_id,
                    ActivityInterval.user_id == user.id,
                    ActivityInterval.work_session_id == session.id,
                    ActivityInterval.source == "unconfirmed_input",
                )
                .order_by(ActivityInterval.started_at, ActivityInterval.id)
            )
        )
        connected: list[ActivityInterval] = []
        merged_start = window_started_at
        merged_end = last_seen_at
        changed = True
        while changed:
            changed = False
            for interval in intervals:
                if interval in connected:
                    continue
                gap = self._interval_gap(
                    merged_start,
                    merged_end,
                    interval.started_at,
                    interval.ended_at,
                )
                candidate_start = min(merged_start, interval.started_at)
                candidate_end = max(merged_end, interval.ended_at)
                if (
                    gap <= self._PRESENCE_GAP
                    and session.contains_working_interval(
                        candidate_start, candidate_end
                    )
                ):
                    connected.append(interval)
                    merged_start = candidate_start
                    merged_end = candidate_end
                    changed = True

        if connected:
            interval = connected[0]
            interval.started_at = merged_start
            interval.ended_at = merged_end
            for duplicate in connected[1:]:
                self.db.delete(duplicate)
        else:
            interval = ActivityInterval.from_evidence(
                session,
                started_at=window_started_at,
                ended_at=last_seen_at,
                source="unconfirmed_input",
            )
            self.db.add(interval)
        interval.closed_at = self._presence_closure_at(session, merged_end)
        self.db.flush()
        self._recompute_durations(session)
        return interval

    def close_stale_presence(self, *, now: datetime) -> int:
        now = self._require_utc_naive(now, "presence closure time")
        cutoff = now - self._PRESENCE_GAP
        eligible = (
            ActivityInterval.source == "unconfirmed_input",
            ActivityInterval.closed_at.is_(None),
            ActivityInterval.ended_at <= cutoff,
        )
        user_ids = list(
            self.db.scalars(
                select(ActivityInterval.user_id)
                .where(*eligible)
                .distinct()
                .order_by(ActivityInterval.user_id)
            )
        )
        count = 0
        for user_id in user_ids:
            user = self.db.get(User, user_id)
            if user is None:
                continue
            self._lock_user(user)
            intervals = list(
                self.db.scalars(
                    select(ActivityInterval).where(
                        *eligible, ActivityInterval.user_id == user_id
                    )
                )
            )
            for interval in intervals:
                interval.closed_at = now
            count += len(intervals)
        self.db.flush()
        return count

    def close_for_status_transition(
        self, session: WorkSession, *, at: datetime
    ) -> int:
        at = self._require_utc_naive(at, "presence transition time")
        intervals = list(
            self.db.scalars(
                select(ActivityInterval).where(
                    ActivityInterval.work_session_id == session.id,
                    ActivityInterval.source == "unconfirmed_input",
                    ActivityInterval.closed_at.is_(None),
                )
            )
        )
        for interval in intervals:
            if interval.started_at >= at:
                self.db.delete(interval)
            else:
                if interval.ended_at > at:
                    interval.ended_at = at
                interval.closed_at = at
        self.db.flush()
        self._recompute_durations(session)
        return len(intervals)

    def _lock_user(self, user: User) -> None:
        self.db.execute(
            select(User.id)
            .where(User.id == user.id, User.amocrm_account_id == user.amocrm_account_id)
            .with_for_update()
        ).scalar_one()

    def _verified_user(self, event: CrmEvent | CallEvent) -> User | None:
        if (
            event.user_id is None
            or event.author_amocrm_user_id is None
            or event.author_amocrm_user_id <= 0
        ):
            return None
        user = self.db.get(User, event.user_id)
        if (
            user is None
            or user.amocrm_account_id != event.account_id
            or user.amocrm_user_id != event.author_amocrm_user_id
        ):
            return None
        return user

    def _working_session(
        self, user: User, started_at: datetime, ended_at: datetime
    ) -> WorkSession | None:
        sessions = self.db.scalars(
            select(WorkSession)
            .where(
                WorkSession.amocrm_account_id == user.amocrm_account_id,
                WorkSession.amocrm_user_id == user.amocrm_user_id,
                WorkSession.start_time <= started_at,
                or_(WorkSession.end_time.is_(None), WorkSession.end_time >= ended_at),
            )
            .order_by(WorkSession.start_time.desc(), WorkSession.id.desc())
        )
        return next(
            (
                session
                for session in sessions
                if session.contains_working_interval(started_at, ended_at)
            ),
            None,
        )

    def _interval_for_batch(
        self, batch: PresenceBatch, user: User
    ) -> ActivityInterval | None:
        session = self._working_session(
            user, batch.window_started_at, batch.last_seen_at
        )
        if session is None:
            return None
        return self.db.scalar(
            select(ActivityInterval)
            .where(
                ActivityInterval.account_id == batch.account_id,
                ActivityInterval.user_id == batch.user_id,
                ActivityInterval.work_session_id == session.id,
                ActivityInterval.source == "unconfirmed_input",
                ActivityInterval.started_at <= batch.window_started_at,
                ActivityInterval.ended_at >= batch.last_seen_at,
            )
            .order_by(ActivityInterval.id)
        )

    def _validate_presence_times(
        self,
        *,
        window_started_at: datetime,
        last_seen_at: datetime,
        received_at: datetime,
    ) -> None:
        for value in (window_started_at, last_seen_at, received_at):
            self._require_utc_naive(value, "presence timestamp")
        if window_started_at > last_seen_at:
            raise ValueError("presence timestamps are out of order")
        if window_started_at > received_at or last_seen_at > received_at:
            raise ValueError("presence timestamp is in the future")
        oldest = received_at - self._PRESENCE_MAX_AGE
        if window_started_at < oldest or last_seen_at < oldest:
            raise ValueError("presence timestamp is too old")

    def _presence_closure_at(
        self, session: WorkSession, ended_at: datetime
    ) -> datetime | None:
        transition_at = self.db.scalar(
            select(StatusTransition.timestamp)
            .where(
                StatusTransition.work_session_id == session.id,
                StatusTransition.timestamp >= ended_at,
                StatusTransition.to_status != WorkStatus.WORKING.value,
            )
            .order_by(StatusTransition.timestamp, StatusTransition.id)
            .limit(1)
        )
        if transition_at is not None:
            return self._utc_naive(transition_at)
        if session.end_time is not None and session.end_time >= ended_at:
            return self._utc_naive(session.end_time)
        return None

    def _recompute_durations(self, session: WorkSession) -> None:
        rows = list(
            self.db.scalars(
                select(ActivityInterval).where(
                    ActivityInterval.work_session_id == session.id
                )
            )
        )
        confirmed = self._merge_ranges(
            (row.started_at, row.ended_at)
            for row in rows
            if row.kind == "confirmed"
            and row.duration_source in {"observed", "calculated"}
            and row.ended_at > row.started_at
        )
        neutral = self._merge_ranges(
            (row.started_at, row.ended_at)
            for row in rows
            if row.kind == "unconfirmed" and row.ended_at > row.started_at
        )
        active_seconds = self._range_seconds(confirmed)
        neutral_seconds = self._range_seconds(neutral)
        overlap_seconds = self._overlap_seconds(neutral, confirmed)
        session.active_duration = active_seconds
        session.unconfirmed_duration = max(0, neutral_seconds - overlap_seconds)
        self.db.flush()

    @staticmethod
    def _merge_ranges(ranges):
        merged: list[list[datetime]] = []
        for start, end in sorted(ranges):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            elif end > merged[-1][1]:
                merged[-1][1] = end
        return merged

    @staticmethod
    def _range_seconds(ranges) -> int:
        return int(sum((end - start).total_seconds() for start, end in ranges))

    @staticmethod
    def _overlap_seconds(left, right) -> int:
        seconds = 0.0
        for left_start, left_end in left:
            for right_start, right_end in right:
                start = max(left_start, right_start)
                end = min(left_end, right_end)
                if end > start:
                    seconds += (end - start).total_seconds()
        return int(seconds)

    @staticmethod
    def _interval_gap(first_start, first_end, second_start, second_end):
        if first_end < second_start:
            return second_start - first_end
        if second_end < first_start:
            return first_start - second_end
        return timedelta(0)

    @staticmethod
    def _require_utc_naive(value: datetime, label: str) -> datetime:
        if not isinstance(value, datetime) or value.tzinfo is not None:
            raise ValueError(f"{label} must be UTC-naive")
        return value

    @staticmethod
    def _utc_naive(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)
