from datetime import datetime, timedelta, timezone

from app.core.activity_timeline_range import activity_timeline_bounds


DAY_START = datetime(2026, 10, 24)
DAY_END = datetime(2026, 10, 25)


def test_uses_schedule_when_day_has_no_sessions():
    result = activity_timeline_bounds(
        day_start=DAY_START,
        day_end=DAY_END,
        scheduled_start=datetime(2026, 10, 24, 9),
        scheduled_end=datetime(2026, 10, 24, 17),
        sessions=[
            (datetime(2026, 10, 23, 8), datetime(2026, 10, 23, 16)),
            (datetime(2026, 10, 25, 8), datetime(2026, 10, 25, 16)),
        ],
        now=datetime(2026, 10, 24, 12),
    )

    assert result == (
        datetime(2026, 10, 24, 9),
        datetime(2026, 10, 24, 17),
    )


def test_extends_short_session_to_eight_hours():
    result = activity_timeline_bounds(
        day_start=DAY_START,
        day_end=DAY_END,
        scheduled_start=datetime(2026, 10, 24, 9),
        scheduled_end=datetime(2026, 10, 24, 18),
        sessions=[(datetime(2026, 10, 24, 9), datetime(2026, 10, 24, 12))],
        now=datetime(2026, 10, 24, 15),
    )

    assert result == (
        datetime(2026, 10, 24, 9),
        datetime(2026, 10, 24, 17),
    )


def test_extends_to_overtime_end():
    result = activity_timeline_bounds(
        day_start=DAY_START,
        day_end=DAY_END,
        scheduled_start=datetime(2026, 10, 24, 9),
        scheduled_end=datetime(2026, 10, 24, 18),
        sessions=[(datetime(2026, 10, 24, 9), datetime(2026, 10, 24, 20, 30))],
        now=datetime(2026, 10, 24, 21),
    )

    assert result == (
        datetime(2026, 10, 24, 9),
        datetime(2026, 10, 24, 20, 30),
    )


def test_combines_multiple_sessions():
    result = activity_timeline_bounds(
        day_start=DAY_START,
        day_end=DAY_END,
        scheduled_start=datetime(2026, 10, 24, 9),
        scheduled_end=datetime(2026, 10, 24, 18),
        sessions=[
            (datetime(2026, 10, 24, 8), datetime(2026, 10, 24, 10)),
            (datetime(2026, 10, 24, 14), datetime(2026, 10, 24, 18)),
        ],
        now=datetime(2026, 10, 24, 19),
    )

    assert result == (
        datetime(2026, 10, 24, 8),
        datetime(2026, 10, 24, 18),
    )


def test_open_session_uses_fixed_now():
    result = activity_timeline_bounds(
        day_start=DAY_START,
        day_end=DAY_END,
        scheduled_start=datetime(2026, 10, 24, 9),
        scheduled_end=datetime(2026, 10, 24, 18),
        sessions=[(datetime(2026, 10, 24, 9), None)],
        now=datetime(2026, 10, 24, 11, 15),
    )

    assert result == (
        datetime(2026, 10, 24, 9),
        datetime(2026, 10, 24, 17),
    )


def test_overnight_range_stays_positive_and_contains_session():
    result = activity_timeline_bounds(
        day_start=datetime(2026, 10, 24, tzinfo=timezone.utc),
        day_end=datetime(2026, 10, 25, tzinfo=timezone.utc),
        scheduled_start=datetime(2026, 10, 24, 22, tzinfo=timezone.utc),
        scheduled_end=datetime(2026, 10, 25, 6, tzinfo=timezone.utc),
        sessions=[
            (
                datetime(2026, 10, 24, 22, tzinfo=timezone.utc),
                datetime(2026, 10, 25, 7, tzinfo=timezone.utc),
            )
        ],
        now=datetime(2026, 10, 25, 8, tzinfo=timezone.utc),
        minimum=timedelta(hours=8),
    )

    assert result == (
        datetime(2026, 10, 24, 22),
        datetime(2026, 10, 25, 7),
    )
    assert result[1] > result[0]
