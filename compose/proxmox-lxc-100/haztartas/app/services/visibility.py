"""Who may see and change which entry. The one place these rules live.

Every list, report, export, photo and audio URL goes through here: a hidden
entry leaks from a caller that skips this module, never from inside it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.sql.elements import ColumnElement

from app.models import Entry, User, Wallet

View = Literal["full", "redacted", "none"]


@dataclass(frozen=True)
class RedactedEntry:
    """What a non-author sees of someone else's secret entry. Templates get
    this, never the ORM row, so merchant and note cannot be reached."""
    id: int
    amount_minor: int
    currency: str
    eur_minor: int
    category_id: int | None
    date: str
    created_by: int
    hidden: bool


def is_secret(entry: Entry, today: str) -> bool:
    return bool(entry.hidden) and (entry.reveal_on is None
                                   or entry.reveal_on > today)


def _check_wallet(entry: Entry, wallet: Wallet) -> None:
    # Not an assert: asserts vanish under -O, and a wrong wallet leaks.
    if wallet.id != entry.wallet_id:
        raise ValueError("wallet is not the entry's wallet")


def view_of(viewer: User, entry: Entry, wallet: Wallet, today: str) -> View:
    _check_wallet(entry, wallet)
    # The transfer_group row of the rule table only affects can_edit.
    if entry.deleted_at is not None:
        return "none"
    if entry.created_by == viewer.id:
        return "full"
    secret = is_secret(entry, today)
    if viewer.role == "adult":
        return "redacted" if secret else "full"
    # A child: own wallet (a parent's top-up) in full, unless it is a secret.
    if wallet.owner_user_id == viewer.id and not secret:
        return "full"
    return "none"


def can_edit(viewer: User, entry: Entry, wallet: Wallet, today: str) -> bool:
    _check_wallet(entry, wallet)
    if entry.deleted_at is not None or entry.transfer_group is not None:
        return False
    if entry.created_by == viewer.id:
        return True
    return viewer.role == "adult" and not is_secret(entry, today)


def present(viewer: User, entry: Entry, wallet: Wallet,
            today: str) -> Entry | RedactedEntry | None:
    view = view_of(viewer, entry, wallet, today)
    if view == "full":
        return entry
    if view == "redacted":
        return RedactedEntry(
            id=entry.id, amount_minor=entry.amount_minor,
            currency=entry.currency, eur_minor=entry.eur_minor,
            category_id=entry.category_id, date=entry.date,
            created_by=entry.created_by, hidden=bool(entry.hidden))
    return None


def _secret(today: str) -> ColumnElement[bool]:
    return and_(Entry.hidden != 0,
                or_(Entry.reveal_on.is_(None), Entry.reveal_on > today))


def listable(viewer: User, today: str) -> ColumnElement[bool]:
    """Rows the viewer may see at all. Correct with or without a Wallet join."""
    alive = Entry.deleted_at.is_(None)
    if viewer.role == "adult":
        return alive
    return and_(alive, or_(
        Entry.created_by == viewer.id,
        and_(Entry.wallet_id.in_(
            select(Wallet.id).where(Wallet.owner_user_id == viewer.id)),
            not_(_secret(today)))))


def text_searchable(viewer: User, today: str) -> ColumnElement[bool]:
    """Rows whose merchant, note or transcript this viewer's search may match."""
    return or_(Entry.created_by == viewer.id, not_(_secret(today)))
