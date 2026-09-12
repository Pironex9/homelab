"""Display formatting for templates.

Not named format: as a module it would shadow the builtin in every file that
imports it by name.

Separate from main.py so that formatting money does not require a signing key:
importing app.main runs config.load(), which refuses to start without the
secrets, and that has nothing to do with turning 2500 into "25,00 EUR".
"""
from __future__ import annotations


def eur(cents: int) -> str:
    """Integer cents -> "25,00 EUR". Never a float: the column is integer cents
    precisely so no float touches money, and a filter is the last place to
    reintroduce one.

    The sign comes off first. Python's // and % floor towards minus infinity,
    so -150 // 100 is -2 and -150 % 100 is 50, which would render minus one
    euro fifty as "-2,50 EUR".
    """
    # A SUM() or AVG() comes back from SQLite as a float, and a nullable
    # column comes back as None. Neither may turn a whole page into a 500 on
    # the way to displaying a price.
    cents = round(cents or 0)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}{cents // 100},{cents % 100:02d} EUR"


def qty(value: float | None) -> str:
    """A stock quantity, at most two decimals, comma as the separator.

    Trailing zeros come off, so three whole bottles read "3" and not "3,00",
    while a part used one reads "3,4". Rounded for display only: the stored
    value keeps its full precision, because rounding every consumption to two
    places would drift the shelf figure by a bottle a year.
    """
    text = f"{round(float(value or 0.0), 2):.2f}".rstrip("0").rstrip(".")
    return (text or "0").replace(".", ",")
