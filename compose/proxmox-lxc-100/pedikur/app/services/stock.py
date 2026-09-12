"""Stock is a sum, not a stored number.

There is no current_stock column anywhere: a Product's quantity is SUM(qty)
over its Stock Movements. Instant at this scale, and it removes the class of
bug where the movements and the stored figure drift apart with nothing to
notice it.

Movements are append-only. Nothing in this module edits or deletes a row. A
correction is another row, a mistake is another row, and undoing an expense is
another row. That rule is what makes the sum trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, StockMovement
from app.services import products, timeutil

REASONS = ("purchase", "opening", "consumption", "sale", "correction", "waste")
# What a human may pick on the stock screen. purchase belongs to the expense
# form, where it is typed once together with the money; consumption and sale
# are posted by the close path and must never be typed by hand, or the ledger
# would carry two entries for one bottle.
#
# correction leads because the select renders its first entry as the default,
# and on a product that already exists opening is the one wrong answer: its
# opening balance was recorded when it was created, and a second one would
# quietly double the shelf.
MANUAL_REASONS = ("correction", "waste", "opening")
# Anything that puts stock on the shelf, and therefore carries a real price.
INBOUND = ("purchase", "opening")

# Quantities are floats on purpose: a third of a bottle is a third of a
# bottle. The price of that is that a sum computed in Python and the same sum
# computed by SQLite can differ in the last bit, so comparisons in this module
# go against this rather than against zero.
QTY_EPSILON = 1e-9


@dataclass(frozen=True)
class Level:
    product: Product
    qty: float

    @property
    def below_min(self) -> bool:
        """Strictly below. Exactly at the minimum is not yet a warning, or the
        screen is orange on the day she restocks to precisely min_stock."""
        return self.qty < self.product.min_stock


def record(session: Session, product_id: int, qty: float, reason: str,
           created_by: str, unit_cost_cents: int = 0,
           visit_id: int | None = None, expense_id: int | None = None,
           note: str | None = None) -> StockMovement:
    """Append one movement. Positive puts stock on the shelf, negative takes
    it off.

    Both guards are also CHECK constraints in 004_phase2.sql, and the product
    lookup is also a foreign key. They are repeated here because an
    IntegrityError surfaces at commit, by which time the route has left its
    try block and the user sees a 500 instead of a message.
    """
    if reason not in REASONS:
        raise ValueError(f"not a stock movement reason: {reason!r}")
    if abs(float(qty)) < QTY_EPSILON:
        raise ValueError("a stock movement of zero is not a movement")
    products.get(session, product_id)   # LookupError rather than IntegrityError
    movement = StockMovement(
        product_id=product_id, qty=float(qty), reason=reason,
        unit_cost_cents=int(unit_cost_cents), visit_id=visit_id,
        expense_id=expense_id, note=note, created_by=created_by,
        created_at=timeutil.to_utc_iso(timeutil.local_now()))
    session.add(movement)
    session.flush()
    return movement


def quantity(session: Session, product_id: int) -> float:
    """SUM over an empty set is NULL, which would reach a template as None and
    render "None flakon"."""
    total = session.scalar(
        select(func.sum(StockMovement.qty))
        .where(StockMovement.product_id == product_id))
    return float(total or 0.0)


def last_cost_cents(session: Session, product_id: int) -> int:
    """What to charge an outbound movement with: the price of the most recent
    inbound one.

    Zero when nothing was ever bought, rather than an exception. A consumption
    posted at zero cost is a missing margin on one line; a raised exception is
    a failed close with a client in the chair. The stock screen shows which
    products have no price, so the gap is visible rather than silent.

    Ordered by id as well as created_at: two movements written inside one
    transaction share a timestamp to the second, and the tie has to break
    towards the later row.
    """
    row = session.scalars(
        select(StockMovement)
        .where(StockMovement.product_id == product_id,
               StockMovement.reason.in_(INBOUND))
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(1)).first()
    return row.unit_cost_cents if row is not None else 0


def levels(session: Session, include_archived: bool = False) -> list[Level]:
    """Every product with its computed quantity. Two queries, not one per
    product: at a few dozen products the N+1 would not be slow, but the shape
    is what gets copied into the dashboard later, where it would be."""
    sums = dict(session.execute(
        select(StockMovement.product_id, func.sum(StockMovement.qty))
        .group_by(StockMovement.product_id)).all())
    return [Level(product=p, qty=float(sums.get(p.id) or 0.0))
            for p in products.list_all(session, include_archived)]
