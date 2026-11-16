"""Month summary for the household wallet, and per-wallet balances.

Household totals read only the household wallet (owner_user_id IS NULL), only
confirmed and not deleted rows. Secret entries count in full: the summary is
adult-only and adults see every amount. Integer sums only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import case, func, or_, select

from app.clock import scheduled_day
from app.models import Category, Entry, Recurring, User, Wallet
from app.services import visibility

_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


@dataclass
class CategoryLine:
    category_id: int
    name: str
    spent_eur_minor: int
    limit_eur_minor: int | None


@dataclass
class ExpectedIncome:
    name: str
    day: str
    amount_minor: int
    currency: str


@dataclass
class MonthSummary:
    month: str
    categories: list[CategoryLine]
    income_eur_minor: int
    expense_eur_minor: int
    balance_eur_minor: int
    by_author: list[tuple[str, int]]
    expected: list[ExpectedIncome]


def _valid_month(month: str) -> str:
    if not isinstance(month, str) or not _MONTH.fullmatch(month):
        raise ValueError("month must be YYYY-MM")
    return month


def _household_id(s) -> int:
    return s.scalars(select(Wallet.id).where(
        Wallet.owner_user_id.is_(None))).one()


def month_summary(s, month: str, today: str) -> MonthSummary:
    """Callers: adults only. `today` is kept for the caller's signature; the
    summary does not depend on it (adults see secrets in full)."""
    _valid_month(month)
    base = (Entry.wallet_id == _household_id(s), Entry.status == "confirmed",
            Entry.deleted_at.is_(None), Entry.date.like(f"{month}-%"))

    spent = dict(s.execute(
        select(Entry.category_id, func.coalesce(func.sum(Entry.eur_minor), 0))
        .where(*base, Entry.kind == "expense", Entry.category_id.is_not(None))
        .group_by(Entry.category_id)).all())
    cats = s.scalars(select(Category).where(Category.kind == "expense")
                     .order_by(Category.sort, Category.id)).all()
    lines = []
    for c in cats:
        total = int(spent.get(c.id, 0))
        if c.archived_at is not None:
            # History must add up: keep an archived category that has spending.
            if total == 0:
                continue
        elif total == 0 and c.monthly_limit_eur_minor is None:
            continue
        lines.append(CategoryLine(c.id, c.name, total,
                                  c.monthly_limit_eur_minor))

    income, expense = s.execute(select(
        func.coalesce(func.sum(case((Entry.kind == "income", Entry.eur_minor),
                                    else_=0)), 0),
        func.coalesce(func.sum(case((Entry.kind == "expense", Entry.eur_minor),
                                    else_=0)), 0),
    ).where(*base)).one()

    by_author = [(name, int(total)) for name, total in s.execute(
        select(User.name, func.sum(Entry.eur_minor))
        .join(User, User.id == Entry.created_by)
        .where(*base, Entry.kind == "expense")
        .group_by(User.id, User.name)
        .order_by(func.sum(Entry.eur_minor).desc(), User.name)).all()]

    # Settled for the month: confirmed, or deleted ("not this month", the same
    # rule recurring._exists uses to make no other draft). Only a live draft
    # or no entry at all is still expected.
    confirmed = set(s.scalars(select(Entry.recurring_id).where(
        or_(Entry.status == "confirmed", Entry.deleted_at.is_not(None)),
        Entry.recurring_id.is_not(None), Entry.recurring_month == month)))
    expected = sorted(
        (ExpectedIncome(r.name, scheduled_day(month, r.day_of_month),
                        r.amount_minor, r.currency)
         for r in s.scalars(select(Recurring).where(
             Recurring.kind == "income", Recurring.archived_at.is_(None)))
         if r.id not in confirmed),
        key=lambda e: (e.day, e.name))

    return MonthSummary(month, lines, int(income), int(expense),
                        int(income) - int(expense), by_author, expected)


def wallet_balance(s, wallet_id: int, viewer: User, today: str) -> int:
    """EUR minor, income minus expense of the confirmed rows of one wallet that
    the viewer may see. A child's balance therefore excludes an adult's secret
    gift until its reveal date."""
    inc, exp = s.execute(select(
        func.coalesce(func.sum(case((Entry.kind == "income", Entry.eur_minor),
                                    else_=0)), 0),
        func.coalesce(func.sum(case((Entry.kind == "expense", Entry.eur_minor),
                                    else_=0)), 0),
    ).where(Entry.wallet_id == wallet_id, Entry.status == "confirmed",
            visibility.listable(viewer, today))).one()
    return int(inc) - int(exp)
