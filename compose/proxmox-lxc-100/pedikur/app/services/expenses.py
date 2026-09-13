"""Money out, and the stock it sometimes brings in.

Category comes from a fixed list rather than free text: free text would give
the dashboard four spellings of one category within two months, and no way to
merge them afterwards. The keys are ASCII and the Hungarian labels live in
app/strings/hu.py.

An expense with no line items is just an expense. An expense with line items is
also a delivery, and typing it once is the whole reason the two live on one
form: the second entry is the one that gets skipped, and after that the shelf
and the database disagree with nothing to notice it.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense, StockMovement
from app.services import products, stock, timeutil

CATEGORIES = ("anyag", "eszkoz", "berleti_dij", "rezsi", "marketing", "egyeb")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_AMOUNT_CENTS = 1_000_000_00   # a practice, not a building purchase


def create(session: Session, date: str, category: str, amount_cents: int,
           created_by: str, vendor: str | None = None, note: str | None = None,
           lines: Sequence[tuple[int, float, int]] = ()) -> Expense:
    """One expense, plus one inbound Stock Movement per line item.

    All in one session, so a bad line leaves no expense behind. A recorded
    expense whose line was silently dropped is worse than a refused form:
    nothing on any screen would say the stock is short.
    """
    if category not in CATEGORIES:
        raise ValueError(f"not an expense category: {category!r}")
    if not DATE.match(date or ""):
        # Also a CHECK constraint, but an IntegrityError surfaces at commit,
        # after the route has left its try block, and the user sees a 500.
        raise ValueError(f"not a calendar date: {date!r}")
    amount = int(amount_cents)
    if amount < 0:
        raise ValueError("an expense cannot be negative")
    if amount > MAX_AMOUNT_CENTS:
        raise ValueError(f"amount out of range: {amount}")

    # Every line is checked before the expense row exists, not while the
    # movements are written. Rolling back on the exception is not enough on
    # its own: a caller that catches it inside its own session block still
    # commits whatever was flushed first, and then the money is recorded and
    # the stock is not, with nothing on any screen to say so.
    for product_id, qty, _ in lines:
        if float(qty) <= 0:
            raise ValueError("a purchased quantity has to be positive")
        products.get(session, product_id)   # LookupError before anything exists

    expense = Expense(date=date, category=category, amount_cents=amount,
                      vendor=(vendor or "").strip() or None,
                      note=(note or "").strip() or None, created_by=created_by,
                      created_at=timeutil.to_utc_iso(timeutil.local_now()))
    session.add(expense)
    session.flush()
    for product_id, qty, unit_cost_cents in lines:
        stock.record(session, product_id, float(qty), "purchase",
                     created_by=created_by,
                     unit_cost_cents=int(unit_cost_cents),
                     expense_id=expense.id)
    return expense


def recent(session: Session, limit: int = 100) -> list[Expense]:
    """Newest first, deleted ones out.

    No period filter. Periods belong to the dashboard in phase 4, and until
    then a flat list of the last hundred is the whole requirement: at thirty
    to sixty purchase documents a year that is well over a year of history.
    """
    return list(session.scalars(
        select(Expense)
        .where(Expense.deleted_at.is_(None))
        .order_by(Expense.date.desc(), Expense.id.desc())
        .limit(limit)))


def line_total_cents(session: Session, expense_id: int) -> int:
    """What the line items add up to, for comparison against the amount.

    Reported, never enforced. She may have bought a coffee on the same
    receipt, and a form that refuses the real receipt is a form she stops
    filling in. The screen shows the difference so it is visible rather than
    silent.
    """
    total = session.scalar(
        select(func.sum(StockMovement.qty * StockMovement.unit_cost_cents))
        .where(StockMovement.expense_id == expense_id,
               StockMovement.reason == "purchase"))
    return int(round(total or 0))


def delete(session: Session, expense_id: int, created_by: str) -> None:
    """Soft delete, and reverse the stock it brought in.

    Without the reversal the ledger keeps claiming two bottles that were never
    bought, and every later consumption is charged at a price that never
    existed.

    The reversal is a new movement, not an edit of the purchase: the ledger is
    append-only, and a row that can be deleted cannot be audited. Idempotent,
    because deleting twice must not take the stock off twice; deleted_at is
    what tells the second call apart.
    """
    expense = session.get(Expense, expense_id)
    if expense is None:
        raise LookupError(f"no expense {expense_id}")
    if expense.deleted_at is not None:
        return
    for row in list(session.scalars(
            select(StockMovement)
            .where(StockMovement.expense_id == expense_id,
                   StockMovement.reason == "purchase"))):
        stock.record(session, row.product_id, -row.qty, "correction",
                     created_by=created_by,
                     unit_cost_cents=row.unit_cost_cents,
                     expense_id=expense_id,
                     note=f"reversal of expense {expense_id}")
    expense.deleted_at = timeutil.to_utc_iso(timeutil.local_now())
    session.flush()
