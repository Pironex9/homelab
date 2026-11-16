"""Amounts in and out. Money is integer minor units (hundredths), every currency."""
from __future__ import annotations

import re

# A dot followed by exactly three digits is a thousands separator ("1.200");
# a comma or dot followed by one or two digits is the decimal mark. "12,345"
# is ambiguous and rejected. A space is a thousands separator only between
# groups of exactly three digits ("1 200", "12 000"); "12 50" is a typo.
_SPACED = re.compile(r"[0-9]{1,3}(?: [0-9]{3})+(?:[.,][0-9]{1,2})?")
_AMOUNT = re.compile(
    r"([1-9][0-9]{0,2}(?:\.[0-9]{3})+|[0-9]+)(?:[.,]([0-9]{1,2}))?")


# 10 billion major units (10**12 minor units): far above any household
# figure, far below what SQLite or Decimal arithmetic chokes on.
MAX_MINOR = 10 ** 12


def parse_amount(text: str) -> int:
    # A no-break space is how many keyboards and copy-pastes write "1 200".
    cleaned = text.replace("\u00a0", " ").replace("\u202f", " ").strip()
    if " " in cleaned:
        if not _SPACED.fullmatch(cleaned):
            raise ValueError(f"not an amount: {text!r}")
        cleaned = cleaned.replace(" ", "")
    m = _AMOUNT.fullmatch(cleaned)
    if not m:
        raise ValueError(f"not an amount: {text!r}")
    whole = int(m.group(1).replace(".", ""))
    cents = int((m.group(2) or "0").ljust(2, "0"))
    minor = whole * 100 + cents
    if minor <= 0:
        raise ValueError("amount must be positive")
    if minor > MAX_MINOR:
        raise ValueError("amount too large")
    return minor


def fmt_money(minor: int, currency: str) -> str:
    sign = "-" if minor < 0 else ""
    whole, cents = divmod(abs(minor), 100)
    grouped = f"{whole:,}".replace(",", " ")
    if currency == "HUF":
        frac = f",{cents:02d}" if cents else ""
        return f"{sign}{grouped}{frac} Ft"
    return f"{sign}{grouped},{cents:02d} {currency}"


def fmt_eur_short(minor: int) -> str:
    """Whole euros, half away from zero: "312 €". For map tiles only, where a
    narrow tile must still show its magnitude; exact cents live in the lists."""
    sign = "-" if minor < 0 else ""
    whole = (abs(minor) + 50) // 100
    return f"{sign}{whole:,} €".replace(",", " ")
