"""Recurring items (salary, rent, subscriptions) and the drafts they create.

A draft is an ordinary entry with status 'draft', created through
entries.create_entry so validation and EUR conversion live in one place. A
person confirms it (or corrects the amount: net pay varies) before it counts.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.clock import scheduled_day, today as _today
from app.models import Entry, Recurring, User, Wallet
from app.services import entries
from app.services.entries import EntryInput, NeedsRate, NotAllowed

log = logging.getLogger(__name__)

INTERVAL_SECONDS = 60 * 60


def _exists(s, recurring_id: int, month: str) -> bool:
    # Deleted drafts count too: the UNIQUE index does, and a deleted draft
    # means "not this month", not "make another".
    return s.scalar(select(Entry.id).where(
        Entry.recurring_id == recurring_id,
        Entry.recurring_month == month)) is not None


def create_due_drafts(s, today: str) -> int:
    """One draft per active item whose day this month has come. Idempotent."""
    month = today[:7]
    household = s.scalars(select(Wallet).where(
        Wallet.owner_user_id.is_(None))).one()
    first_adult = s.scalars(select(User).where(User.role == "adult")
                            .order_by(User.id)).first()
    made = 0
    for r in s.scalars(select(Recurring).where(
            Recurring.archived_at.is_(None)).order_by(Recurring.id)):
        day = scheduled_day(month, r.day_of_month)
        if day > today or _exists(s, r.id, month):
            continue
        author = (s.get(User, r.owner_user_id) if r.owner_user_id
                  else first_adult)
        if author is None:
            log.warning("recurring %r: no user to author the draft", r.name)
            continue
        data = EntryInput(
            wallet_id=household.id, kind=r.kind, date=day,
            amount_minor=r.amount_minor, currency=r.currency,
            category_id=r.category_id, merchant=r.name, note=None,
            payment="other", hidden=False, reveal_on=None, source="recurring",
            recurring_id=r.id, recurring_month=month)
        try:
            # Savepoint: a lost race rolls back only this insert.
            with s.begin_nested():
                entries.create_entry(s, author, data, status="draft")
        except NeedsRate:
            log.warning("recurring %r: no %s rate for %s yet, retrying next "
                        "run", r.name, r.currency, day)
            continue
        except IntegrityError:
            continue   # UNIQUE(recurring_id, recurring_month): already made
        except (ValueError, NotAllowed):
            log.exception("recurring %r: draft refused", r.name)
            continue
        made += 1
    return made


def confirm_draft(s, adult: User, entry_id: int,
                  data: EntryInput | None) -> Entry:
    if adult.role != "adult":
        raise NotAllowed("only an adult can confirm a draft")
    e = s.get(Entry, entry_id)
    if e is None or e.deleted_at is not None:
        raise NotAllowed("no such draft")
    if e.status != "draft":
        raise ValueError("entry is not a draft")
    if data is not None:
        e = entries.update_entry(s, adult, entry_id, data)
    e.status = "confirmed"
    s.flush()
    return e


async def daily_task(db, interval: float = INTERVAL_SECONDS,
                     today: Callable[[], str] = _today,
                     sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                     ) -> None:
    """Run at start and hourly: cheap and idempotent, so a container restarted
    at 00:30 still catches the day."""
    while True:
        try:
            with db.session() as s:
                n = create_due_drafts(s, today())
            if n:
                log.info("created %d recurring drafts", n)
        except Exception:  # must not kill the app
            log.exception("recurring drafts failed")
        await sleep(interval)
