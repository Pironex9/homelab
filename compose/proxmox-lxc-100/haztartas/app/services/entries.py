"""Create, change, delete and de-duplicate entries.

Who may do what to an existing entry is decided by services.visibility; this
module only adds the one rule that is about creating: which wallet a user may
write into.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date as _date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app import fx
from app.clock import now_utc, today
from app.models import Category, Entry, User, Wallet
from app.services import visibility

KINDS = ("expense", "income")
PAYMENTS = ("cash", "card", "other")
STATUSES = ("draft", "confirmed")
_CURRENCY = re.compile(r"[A-Z]{3}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class EntryInput:
    wallet_id: int
    kind: str
    date: str
    amount_minor: int
    currency: str
    category_id: int | None
    merchant: str | None
    note: str | None
    payment: str
    hidden: bool
    reveal_on: str | None
    manual_rate: Decimal | None = None
    client_uuid: str | None = None
    source: str = "manual"


@dataclass
class DuplicateHint:
    entry_id: int
    eur_minor: int
    merchant: str | None   # None when the candidate is a secret of someone else
    author_name: str
    created_at: str | None   # None unless the viewer sees the entry in full
    hidden: bool


class NeedsRate(Exception):
    """No ECB rate for the day and no manual rate given."""


class NotAllowed(Exception):
    """Role, wallet or edit rule refused."""


def _valid_date(value: str, what: str = "date") -> str:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError(f"{what} must be YYYY-MM-DD")
    try:
        _date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{what} is not a real date") from None
    return value


def _validate_money(amount_minor: int, currency: str) -> None:
    if (not isinstance(amount_minor, int) or isinstance(amount_minor, bool)
            or amount_minor <= 0):
        raise ValueError("amount must be a positive integer")
    if not isinstance(currency, str) or not _CURRENCY.fullmatch(currency):
        raise ValueError("currency must be 3 uppercase letters")


def _validate(s, data: EntryInput, keep_category: int | None = None) -> None:
    if data.kind not in KINDS:
        raise ValueError("kind must be expense or income")
    if data.payment not in PAYMENTS:
        raise ValueError("payment must be cash, card or other")
    if data.source is None or not str(data.source):
        raise ValueError("source is required")
    _validate_money(data.amount_minor, data.currency)
    _valid_date(data.date)
    if data.manual_rate is not None and not (
            data.manual_rate.is_finite() and data.manual_rate > 0):
        raise ValueError("manual rate must be a positive finite number")
    if data.category_id is not None:
        c = s.get(Category, data.category_id)
        if c is None or (c.archived_at is not None
                         and data.category_id != keep_category):
            raise ValueError("unknown or archived category")
        if c.kind != data.kind:
            raise ValueError("category kind does not match entry kind")
    if data.reveal_on is not None:
        if not data.hidden:
            raise ValueError("reveal_on only applies to a hidden entry")
        _valid_date(data.reveal_on, "reveal_on")


def _wallet(s, wallet_id: int) -> Wallet:
    w = s.get(Wallet, wallet_id)
    if w is None:
        raise ValueError("unknown wallet")
    return w


def _check_target(s, author: User, wallet: Wallet, kind: str) -> None:
    if wallet.owner_user_id is None:            # household
        ok = author.role == "adult" or kind == "expense"
    elif wallet.owner_user_id == author.id:     # own wallet (a child's)
        ok = True
    else:                                       # someone else's child wallet
        ok = author.role == "adult" and kind == "income"
    if not ok:
        raise NotAllowed("not allowed to add this to that wallet")


def _rate(s, data: EntryInput) -> Decimal | None:
    rate = fx.rate_for(s, data.date, data.currency)
    return rate if rate is not None else data.manual_rate


def _eur(s, data: EntryInput) -> tuple[int, str]:
    rate = _rate(s, data)
    if rate is None:
        raise NeedsRate(f"no rate for {data.currency} on {data.date}")
    return fx.to_eur_minor(data.amount_minor, rate), str(rate)


def create_entry(s, author: User, data: EntryInput,
                 status: str = "confirmed") -> Entry:
    if data.client_uuid:
        existing = s.scalar(select(Entry).where(
            Entry.client_uuid == data.client_uuid))
        if existing is not None:
            if existing.created_by != author.id:
                raise NotAllowed("client_uuid belongs to another user")
            return existing
    if status not in STATUSES:
        raise ValueError("status must be draft or confirmed")
    _validate(s, data)
    _check_target(s, author, _wallet(s, data.wallet_id), data.kind)
    eur_minor, rate = _eur(s, data)
    e = Entry(
        client_uuid=data.client_uuid, wallet_id=data.wallet_id, kind=data.kind,
        status=status, date=data.date, merchant=data.merchant, note=data.note,
        amount_minor=data.amount_minor, currency=data.currency,
        eur_minor=eur_minor, fx_rate=rate, category_id=data.category_id,
        payment=data.payment, hidden=1 if data.hidden else 0,
        reveal_on=data.reveal_on, source=data.source, created_by=author.id,
        created_at=now_utc())
    s.add(e)
    s.flush()
    return e


def _editable(s, viewer: User, entry_id: int) -> tuple[Entry, Wallet]:
    e = s.get(Entry, entry_id)
    if e is None:
        raise NotAllowed("no such entry")
    w = _wallet(s, e.wallet_id)
    if not visibility.can_edit(viewer, e, w, today()):
        raise NotAllowed("this entry cannot be changed by you")
    return e, w


def update_entry(s, viewer: User, entry_id: int, data: EntryInput) -> Entry:
    e, _ = _editable(s, viewer, entry_id)
    _validate(s, data, keep_category=e.category_id)
    if viewer.id != e.created_by and (
            bool(data.hidden) != bool(e.hidden)
            or data.reveal_on != e.reveal_on):
        raise NotAllowed("only the author can hide or unhide an entry")
    if data.wallet_id != e.wallet_id:
        _check_target(s, viewer, _wallet(s, data.wallet_id), data.kind)
    elif data.kind != e.kind:
        _check_target(s, viewer, _wallet(s, e.wallet_id), data.kind)
    if (data.amount_minor, data.currency, data.date) != (
            e.amount_minor, e.currency, e.date):
        e.eur_minor, e.fx_rate = _eur(s, data)
    e.wallet_id, e.kind, e.date = data.wallet_id, data.kind, data.date
    e.amount_minor, e.currency = data.amount_minor, data.currency
    e.category_id, e.merchant, e.note = data.category_id, data.merchant, data.note
    e.payment, e.hidden = data.payment, 1 if data.hidden else 0
    e.reveal_on = data.reveal_on
    e.updated_at = now_utc()
    s.flush()
    return e


def delete_entry(s, viewer: User, entry_id: int) -> None:
    e = s.get(Entry, entry_id)
    if (e is not None and e.transfer_group is not None
            and e.deleted_at is None and viewer.role == "adult"):
        # can_edit refuses transfer rows (a top-up has no edit form), but an
        # adult may undo one; both halves go together.
        rows = list(s.scalars(select(Entry).where(
            Entry.transfer_group == e.transfer_group)))
    else:
        e, _ = _editable(s, viewer, entry_id)
        rows = [e]
    stamp = now_utc()
    for row in rows:
        if row.deleted_at is None:
            row.deleted_at = stamp
    s.flush()


def reveal_entry(s, viewer: User, entry_id: int) -> None:
    e = s.get(Entry, entry_id)
    if e is None or e.deleted_at is not None or e.created_by != viewer.id:
        raise NotAllowed("only the author can reveal an entry")
    e.hidden = 0
    e.reveal_on = None
    e.updated_at = now_utc()
    s.flush()


def find_duplicates(s, viewer: User, data: EntryInput,
                    exclude_id: int | None = None) -> list[DuplicateHint]:
    _valid_date(data.date)
    _validate_money(data.amount_minor, data.currency)
    rate = _rate(s, data)
    if rate is None:
        return []
    mine = fx.to_eur_minor(data.amount_minor, rate)
    day = _date.fromisoformat(data.date)
    days = (data.date, (day - timedelta(days=1)).isoformat())
    wallet = _wallet(s, data.wallet_id)
    q = (select(Entry, User.name).join(User, User.id == Entry.created_by)
         .where(Entry.wallet_id == data.wallet_id, Entry.date.in_(days),
                Entry.status == "confirmed",
                visibility.listable(viewer, today()))
         .order_by(Entry.id))
    if exclude_id is not None:
        q = q.where(Entry.id != exclude_id)
    hints = []
    for e, author_name in s.execute(q):
        if abs(mine - e.eur_minor) * 100 > 2 * max(mine, e.eur_minor):
            continue
        full = visibility.view_of(viewer, e, wallet, today()) == "full"
        hints.append(DuplicateHint(
            entry_id=e.id, eur_minor=e.eur_minor,
            merchant=e.merchant if full else None, author_name=author_name,
            created_at=e.created_at if full else None,
            hidden=visibility.is_secret(e, today())))
    return hints


def top_up(s, adult: User, child_wallet_id: int, amount_minor: int,
           currency: str, day: str) -> tuple[Entry, Entry]:
    if adult.role != "adult":
        raise NotAllowed("only an adult can give pocket money")
    wallet = _wallet(s, child_wallet_id)
    owner = s.get(User, wallet.owner_user_id) if wallet.owner_user_id else None
    if owner is None or owner.role != "child":
        raise NotAllowed("pocket money goes to a child's wallet")
    _validate_money(amount_minor, currency)
    _valid_date(day)
    household = s.scalars(select(Wallet).where(
        Wallet.owner_user_id.is_(None))).one()
    out_cat = s.scalars(select(Category).where(
        Category.name == "Zsebpénz", Category.kind == "expense")).one().id
    in_cat = s.scalars(select(Category).where(
        Category.name == "Egyéb bevétel", Category.kind == "income")).one().id
    group = str(uuid.uuid4())
    made = []
    for wallet_id, kind, cat_id in ((household.id, "expense", out_cat),
                                    (wallet.id, "income", in_cat)):
        data = EntryInput(
            wallet_id=wallet_id, kind=kind, date=day, amount_minor=amount_minor,
            currency=currency, category_id=cat_id, merchant=None, note=None,
            payment="cash", hidden=False, reveal_on=None)
        eur_minor, rate = _eur(s, data)
        e = Entry(
            wallet_id=wallet_id, kind=kind, status="confirmed", date=day,
            amount_minor=amount_minor, currency=currency, eur_minor=eur_minor,
            fx_rate=rate, category_id=cat_id, payment="cash", hidden=0,
            source="manual", created_by=adult.id, created_at=now_utc(),
            transfer_group=group)
        s.add(e)
        made.append(e)
    s.flush()
    return made[0], made[1]
