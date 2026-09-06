"""Instants are stored UTC and rendered local. Working hours are wall clock
and never pass through here: converting 09:00 would move opening time twice a
year in the wrong direction.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Fixed, not read from TZ. The spec names the zone, and a container whose .env
# says TZ=UTC would move every stored instant and every rendered time by an
# hour or two with nothing raising: working_hours stay wall clock by design,
# so the grid and the Visits would just drift apart.
LOCAL = ZoneInfo("Europe/Bratislava")


class NonExistentTime(ValueError):
    """A local wall clock time that the spring forward skipped."""


def local_now() -> datetime:
    return datetime.now(LOCAL)


def as_local(value: datetime) -> datetime:
    """Attach the practice zone to a naive datetime, and refuse a wall clock
    time the spring forward skipped.

    02:30 on the changeover Sunday does not exist. Without this it resolves
    silently to 03:30 and the appointment moves an hour with nothing to show
    for it.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL)
    if value.tzinfo is LOCAL and value.astimezone(timezone.utc).astimezone(LOCAL) != value:
        raise NonExistentTime(f"{value:%Y-%m-%d %H:%M} does not exist in {LOCAL}")
    return value


def to_utc(value: datetime) -> datetime:
    """Local or naive -> aware UTC.

    Everything the booking rules compare goes through here first. Two aware
    datetimes that share a tzinfo object are compared by their wall clock
    fields, with the offset ignored, so across a DST transition an end can
    compare as earlier than its own start while being an hour later in real
    time. In UTC there is no such hour.
    """
    return as_local(value).astimezone(timezone.utc)


def add_minutes(start: datetime, minutes: int) -> datetime:
    """Elapsed time, not wall clock.

    start + timedelta shifts the naive fields and re-resolves the offset
    afterwards, so a 60 minute Visit at 02:30 on the autumn Sunday would be
    stored as a 120 minute block, and one at 01:30 on the spring Sunday as a
    two hour one. Adding in UTC gives the minutes asked for on every day of
    the year. Returns UTC; convert for display, not for arithmetic.
    """
    return start.astimezone(timezone.utc) + timedelta(minutes=minutes)


def to_utc_iso(value: datetime) -> str:
    """Aware or naive local datetime -> "2026-09-10T08:00:00Z".

    The Z form, not isoformat()'s "+00:00": 001_schema.sql's created_at default
    writes Z, and two shapes in one column compare wrong. '+' is 0x2B and 'Z'
    is 0x5A, so a lexicographic BETWEEN over a mixed column silently drops
    half the rows, and every one of these columns is compared as text.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_utc_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL)


def localdate(value: str) -> str:
    return from_utc_iso(value).strftime("%Y. %m. %d.")


def localtime(value: str) -> str:
    return from_utc_iso(value).strftime("%H:%M")
