"""The only source of "today". Entry dates are local calendar dates, so
date.today() (the container's zone, UTC unless TZ is set) must never be used."""
from __future__ import annotations

import calendar
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("Europe/Bratislava")


def today() -> str:
    return datetime.now(LOCAL).date().isoformat()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scheduled_day(month: str, day_of_month: int) -> str:
    """The day of month in a YYYY-MM month, clamped to the month's length."""
    year, mon = int(month[:4]), int(month[5:7])
    day = min(day_of_month, calendar.monthrange(year, mon)[1])
    return f"{month}-{day:02d}"
