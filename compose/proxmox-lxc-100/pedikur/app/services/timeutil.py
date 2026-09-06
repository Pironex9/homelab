"""Instants are stored UTC and rendered local. Working hours are wall clock
and never pass through here: converting 09:00 would move opening time twice a
year in the wrong direction.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Same resolution as config.load(), but readable without the secrets, which
# config refuses to start without.
LOCAL = ZoneInfo(os.environ.get("TZ") or "Europe/Bratislava")


def local_now() -> datetime:
    return datetime.now(LOCAL)


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
