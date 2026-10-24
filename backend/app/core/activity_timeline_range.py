"""Calculate the visible time range for employee activity timelines."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone


def _utc_naive(value: datetime) -> datetime:
    """Match the UTC-naive convention used by persisted service timestamps."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def activity_timeline_bounds(
    *,
    day_start: datetime,
    day_end: datetime,
    scheduled_start: datetime,
    scheduled_end: datetime,
    sessions: Sequence[tuple[datetime, datetime | None]],
    now: datetime,
    minimum: timedelta = timedelta(hours=8),
) -> tuple[datetime, datetime]:
    """Return a stable employee-day range for drawing activity.

    Sessions intersecting the selected day define the natural bounds. An open
    session ends at ``now``. With no sessions, the configured work schedule is
    used. Every returned range is at least ``minimum`` long, while overtime is
    never clipped.
    """

    normalized_day_start = _utc_naive(day_start)
    normalized_day_end = _utc_naive(day_end)
    normalized_schedule_start = _utc_naive(scheduled_start)
    normalized_schedule_end = _utc_naive(scheduled_end)
    normalized_now = _utc_naive(now)

    if normalized_day_end <= normalized_day_start:
        raise ValueError("day_end must be later than day_start")
    if normalized_schedule_end <= normalized_schedule_start:
        raise ValueError("scheduled_end must be later than scheduled_start")
    if minimum <= timedelta(0):
        raise ValueError("minimum must be positive")

    relevant: list[tuple[datetime, datetime]] = []
    for started_at, ended_at in sessions:
        start = _utc_naive(started_at)
        end = normalized_now if ended_at is None else _utc_naive(ended_at)
        if end <= start:
            continue
        if start < normalized_day_end and end > normalized_day_start:
            relevant.append((max(start, normalized_day_start), end))

    if relevant:
        range_start = min(start for start, _ in relevant)
        natural_end = max(end for _, end in relevant)
    else:
        range_start = normalized_schedule_start
        natural_end = normalized_schedule_end

    return range_start, max(natural_end, range_start + minimum)
