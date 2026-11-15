"""Amounts in and out. Money is integer minor units (hundredths), every currency."""
from __future__ import annotations

import re

# A dot followed by exactly three digits is a thousands separator ("1.200");
# a comma or dot followed by one or two digits is the decimal mark. "12,345"
# is ambiguous and rejected. Spaces are thousands separators.
_AMOUNT = re.compile(r"([1-9]\d{0,2}(?:\.\d{3})+|\d+)(?:[.,](\d{1,2}))?")


def parse_amount(text: str) -> int:
    cleaned = re.sub(r"\s+", "", text)
    m = _AMOUNT.fullmatch(cleaned)
    if not m:
        raise ValueError(f"not an amount: {text!r}")
    whole = int(m.group(1).replace(".", ""))
    cents = int((m.group(2) or "0").ljust(2, "0"))
    minor = whole * 100 + cents
    if minor <= 0:
        raise ValueError("amount must be positive")
    return minor


def fmt_money(minor: int, currency: str) -> str:
    sign = "-" if minor < 0 else ""
    whole, cents = divmod(abs(minor), 100)
    grouped = f"{whole:,}".replace(",", " ")
    if currency == "HUF":
        frac = f",{cents:02d}" if cents else ""
        return f"{sign}{grouped}{frac} Ft"
    return f"{sign}{grouped},{cents:02d} {currency}"
