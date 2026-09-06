"""Display formatting for templates.

Not named format: as a module it would shadow the builtin in every file that
imports it by name.

Separate from main.py so that formatting money does not require a signing key:
importing app.main runs config.load(), which refuses to start without the
secrets, and that has nothing to do with turning 2500 into "25,00 EUR".
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def eur(cents: int) -> str:
    """Integer cents -> "25,00 EUR". Never a float: the column is integer cents
    precisely so no float touches money, and a filter is the last place to
    reintroduce one.

    The sign comes off first. Python's // and % floor towards minus infinity,
    so -150 // 100 is -2 and -150 % 100 is 50, which would render minus one
    euro fifty as "-2,50 EUR".
    """
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100},{cents % 100:02d} EUR"


def localdate(iso: str, tz: str) -> str:
    """UTC ISO-8601 text -> a date in the practice's timezone.

    Jinja resolves filter names when it compiles a template, not when it runs
    one, so a template that mentions a missing filter fails to load at all,
    whether or not the loop that uses it has any rows.
    """
    stamp = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return stamp.astimezone(ZoneInfo(tz)).strftime("%Y. %m. %d.")
