from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import fold
from app.models import Treatment

MAX_PRICE_CENTS = 100_000_00   # 100 000 EUR, far above any pedicure


def parse_price(text: str) -> int:
    """"25,00" or "25.00" or "25" -> 2500.

    Decimal, not float: 18.5 * 100 is 1850.0000000000002 in binary floating
    point, and the column refuses anything that is not an integer. Rounding is
    half-up, the way a price list rounds, not banker's rounding.
    """
    cleaned = text.strip().replace(",", ".")
    if not cleaned:
        raise ValueError("empty price")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"not a price: {text!r}") from None
    # Decimal accepts nan, inf and 1E999999 as valid. Without this the
    # comparison below signals InvalidOperation, or the multiplication raises
    # Overflow, and either escapes the route's except ValueError as a 500.
    if not value.is_finite():
        raise ValueError(f"not a price: {text!r}")
    if value < 0:
        raise ValueError("a price cannot be negative")
    try:
        cents = int((value * 100).to_integral_value(rounding="ROUND_HALF_UP"))
    except (ArithmeticError, OverflowError):
        raise ValueError(f"price out of range: {text!r}") from None
    if cents > MAX_PRICE_CENTS:
        # SQLite would take it up to 2**63; a price that long is a typo, and
        # anything past that is an OverflowError at insert time
        raise ValueError(f"price out of range: {text!r}")
    return cents


# SQLite's default BINARY collation sorts every accented initial after Z, so
# "Allo" spelled with its accent lands below "Zsir". fold() is the same UDF the
# client search uses.
def _by_name():
    return func.fold(Treatment.name)


def list_active(session: Session) -> list[Treatment]:
    return list(session.scalars(
        select(Treatment).where(Treatment.active == 1).order_by(_by_name())))


def list_all(session: Session) -> list[Treatment]:
    return list(session.scalars(
        select(Treatment).order_by(Treatment.active.desc(), _by_name())))


def create(session: Session, name: str, duration_min: int,
           price_cents: int, created_by: str) -> Treatment:
    name = name.strip()
    if not name:
        raise ValueError("a treatment needs a name")
    if int(duration_min) <= 0:
        raise ValueError("a treatment needs a duration")
    # Two identical names in the booking dropdown is a support call, not a
    # feature. Compared folded, so "Pedikur" and "PEDIKŰR" are the same name.
    existing = session.scalars(
        select(Treatment).where(func.fold(Treatment.name) == fold(name),
                                Treatment.active == 1)).first()
    if existing is not None:
        raise ValueError(f"a treatment named {name!r} already exists")
    treatment = Treatment(name=name, duration_min=int(duration_min),
                          price_cents=int(price_cents), active=1,
                          created_by=created_by)
    session.add(treatment)
    session.flush()
    return treatment


def update(session: Session, treatment_id: int, **fields) -> Treatment:
    treatment = session.get(Treatment, treatment_id)
    if treatment is None:
        raise LookupError(f"no treatment {treatment_id}")
    for key, value in fields.items():
        setattr(treatment, key, value)
    session.flush()
    return treatment


def deactivate(session: Session, treatment_id: int) -> None:
    """Treatments are never deleted: historical Visit Items point at them."""
    update(session, treatment_id, active=0)


def activate(session: Session, treatment_id: int) -> None:
    update(session, treatment_id, active=1)
