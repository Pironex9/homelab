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

from app.models import Product, StockMovement, Visit
from app.services import products, recipes, timeutil

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


# The two reasons a Visit owns. Everything else on a product's ledger belongs
# to a purchase, an opening balance or a correction, and the reconcile must
# never touch those: they are not its to compute.
VISIT_REASONS = ("consumption", "sale")


def reconcile_visit(session: Session, visit: Visit,
                    created_by: str) -> list[StockMovement]:
    """Make this Visit's stock ledger agree with what the Visit now says.

    Computes what should have gone off the shelf for this Visit, subtracts
    what already has, and appends the difference. Nothing is edited and
    nothing is deleted, so the append-only rule holds.

    Three properties come out of doing it this way rather than posting once on
    the first close:

    - Idempotent by arithmetic. Closing twice computes a difference of zero
      and writes no row, without consulting closed_at or any other flag.
    - Self-healing. A Treatment added or removed after the close moves the
      difference, and the next close writes exactly the correction.
    - Symmetric. A Visit that is not done consumed nothing, so cancelling a
      closed Visit returns its stock through this same function with no second
      code path.
    """
    desired: dict[tuple[int, str], float] = {}
    # Only a done Visit consumes anything. Work that was cancelled or not
    # shown up for used no lacquer, and this one condition is what makes
    # set_status correct without a second implementation.
    if visit.status == "done":
        for item in visit.items:
            if item.kind == "treatment" and item.treatment_id is not None:
                for row in recipes.for_treatment(session, item.treatment_id):
                    key = (row.product_id, "consumption")
                    desired[key] = (desired.get(key, 0.0)
                                    + item.qty / row.treatments_per_unit)
            elif item.kind == "product" and item.product_id is not None:
                key = (item.product_id, "sale")
                desired[key] = desired.get(key, 0.0) + item.qty

    # Stored negative because stock left the shelf; flipped here so both sides
    # of the comparison mean "how much went out".
    posted: dict[tuple[int, str], float] = {
        (product_id, reason): -float(total)
        for product_id, reason, total in session.execute(
            select(StockMovement.product_id, StockMovement.reason,
                   func.sum(StockMovement.qty))
            .where(StockMovement.visit_id == visit.id,
                   StockMovement.reason.in_(VISIT_REASONS))
            .group_by(StockMovement.product_id, StockMovement.reason))}

    written: list[StockMovement] = []
    for key in sorted(set(desired) | set(posted)):
        product_id, reason = key
        delta = desired.get(key, 0.0) - posted.get(key, 0.0)
        # Compared against an epsilon, not against zero: one third of a bottle
        # summed by SQLite over two rows and the same third summed by Python
        # can differ in the last bit, and that difference must not become a
        # movement of 1e-17 on every single close.
        if abs(delta) < QTY_EPSILON:
            continue
        written.append(record(
            session, product_id=product_id, qty=-delta, reason=reason,
            created_by=created_by, visit_id=visit.id,
            unit_cost_cents=last_cost_cents(session, product_id)))
    return written
