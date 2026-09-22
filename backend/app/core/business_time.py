"""Business-calendar conversions for UTC-naive persistence timestamps."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def business_date(
    now_utc: datetime, zone_name: str, start: time, end: time
) -> date:
    """Return the group's workday containing a UTC-naive instant."""
    local_now = now_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(zone_name))
    day = local_now.date()
    if start > end and local_now.timetz().replace(tzinfo=None) < end:
        return day - timedelta(days=1)
    return day


def shift_start_utc(day: date, zone_name: str, start: time) -> datetime:
    """Convert a group's local shift start to a UTC-naive database timestamp."""
    return (
        datetime.combine(day, start, ZoneInfo(zone_name))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


def local_period_utc_bounds(day: date, zone_name: str) -> tuple[datetime, datetime]:
    """Return UTC-naive bounds for one local calendar date."""
    zone = ZoneInfo(zone_name)
    local_start = datetime.combine(day, time.min, zone)
    local_end = datetime.combine(day + timedelta(days=1), time.min, zone)
    return (
        local_start.astimezone(timezone.utc).replace(tzinfo=None),
        local_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def minutes_late(now_utc: datetime, shift_start: datetime) -> int:
    """Return non-negative whole minutes elapsed since the shift began."""
    return max(0, int((now_utc - shift_start).total_seconds() // 60))
