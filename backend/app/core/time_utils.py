"""UTC timestamps compatible with the existing timezone-naive database columns."""

from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
