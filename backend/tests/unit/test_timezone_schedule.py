from datetime import datetime, time


def test_minsk_day_uses_group_calendar():
    """A UTC-day implementation would incorrectly return 2026-09-21."""
    from app.core.business_time import business_date

    assert (
        business_date(
            datetime(2026, 9, 21, 23), "Europe/Minsk", time(9), time(18)
        ).isoformat()
        == "2026-09-22"
    )


def test_overnight_shift_keeps_start_date():
    """Removing the overnight branch would incorrectly return the local date."""
    from app.core.business_time import business_date

    assert (
        business_date(
            datetime(2026, 9, 21, 23), "Europe/Minsk", time(22), time(6)
        ).isoformat()
        == "2026-09-21"
    )


def test_minutes_late_is_zero_before_shift_and_whole_minutes_after_start():
    """A negative or rounded-up delay would report an incorrect lateness."""
    from app.core.business_time import minutes_late

    shift_start = datetime(2026, 9, 22, 6)
    assert minutes_late(datetime(2026, 9, 22, 5, 59, 59), shift_start) == 0
    assert minutes_late(datetime(2026, 9, 22, 6, 7, 59), shift_start) == 7


def test_berlin_dst_midnight_bounds_are_utc_naive_and_cover_local_day():
    """Using a fixed 24-hour UTC day would exclude part of DST transition day."""
    from datetime import date

    from app.core.business_time import local_period_utc_bounds

    assert local_period_utc_bounds(date(2026, 3, 29), "Europe/Berlin") == (
        datetime(2026, 3, 28, 23),
        datetime(2026, 3, 29, 22),
    )
