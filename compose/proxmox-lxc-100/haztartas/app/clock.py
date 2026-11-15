"""The only source of "today". Entry dates are local calendar dates, so
date.today() (the container's zone, UTC unless TZ is set) must never be used."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("Europe/Bratislava")


def today() -> str:
    return datetime.now(LOCAL).date().isoformat()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
