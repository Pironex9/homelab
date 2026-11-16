import re
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, func, or_, select

from app import clock, money
from app.db import fold
from app.models import Category, Entry, User, Wallet
from app.security import require_user
from app.services import entries as svc, visibility
from app.services.home import date_label, hue, shift_month
from app.strings.hu import MONTHS, S

router = APIRouter()

CURRENCIES = ("EUR", "HUF", "CZK", "PLN", "USD", "GBP", "CHF")
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
LIMIT = 300


def _render(request, name, ctx, status=200):
    return request.app.state.templates.TemplateResponse(
        request, name, ctx, status_code=status)


def _choices(s, user: User, entry: Entry | None = None) -> dict:
    keep_cat = entry.category_id if entry else None
    keep_wallet = entry.wallet_id if entry else None
    cats = s.scalars(select(Category).where(or_(
        Category.archived_at.is_(None), Category.id == keep_cat))
        .order_by(Category.kind, Category.sort, Category.id)).all()
    # An adult may write into any wallet (the service decides what is
    # allowed); a child sees the household and their own. An edit always
    # offers the entry's current wallet, or saving would silently move it.
    q = select(Wallet).order_by(Wallet.owner_user_id.is_(None).desc(), Wallet.id)
    if user.role != "adult":
        q = q.where(or_(Wallet.owner_user_id.is_(None),
                        Wallet.owner_user_id == user.id,
                        Wallet.id == keep_wallet))
    wallets = [(w.id, w.name) for w in s.scalars(q)]
    return dict(categories=[(c.id, c.name, c.kind) for c in cats],
                wallets=wallets, currencies=CURRENCIES)


def _amount_text(minor: int) -> str:
    whole, cents = divmod(minor, 100)
    return f"{whole},{cents:02d}"


def _blank_values(s, user: User) -> dict:
    household = s.scalars(select(Wallet).where(
        Wallet.owner_user_id.is_(None))).one()
    return dict(kind="expense", amount="", currency="EUR", date=clock.today(),
                merchant="", note="", category_id="", payment="card",
                wallet_id=str(household.id), hidden="", reveal_on="",
                manual_rate="")


def _entry_values(e: Entry) -> dict:
    return dict(kind=e.kind, amount=_amount_text(e.amount_minor),
                currency=e.currency, date=e.date, merchant=e.merchant or "",
                note=e.note or "", category_id=str(e.category_id or ""),
                payment=e.payment, wallet_id=str(e.wallet_id),
                hidden="1" if e.hidden else "", reveal_on=e.reveal_on or "",
                manual_rate="")


async def _read(request: Request) -> dict:
    f = await request.form()
    keys = ("kind", "amount", "currency", "date", "merchant", "note",
            "category_id", "payment", "wallet_id", "hidden", "reveal_on",
            "manual_rate", "confirm_duplicate")
    return {k: str(f.get(k, "")).strip() for k in keys}


def _build(v: dict) -> svc.EntryInput:
    """Form values to EntryInput. ValueError carries the string key to show."""
    try:
        amount = money.parse_amount(v["amount"])
    except ValueError:
        raise ValueError("amount_invalid") from None
    if _int(v["category_id"]) is None:
        raise ValueError("category_required")
    if _int(v["wallet_id"]) is None:
        raise ValueError("form_invalid")
    rate = None
    if v["manual_rate"]:
        try:
            rate = Decimal(v["manual_rate"].replace(",", "."))
        except InvalidOperation:
            raise ValueError("form_invalid") from None
    hidden = v["hidden"] == "1"
    return svc.EntryInput(
        wallet_id=int(v["wallet_id"]), kind=v["kind"], date=v["date"],
        amount_minor=amount, currency=v["currency"].upper(),
        category_id=int(v["category_id"]), merchant=v["merchant"] or None,
        note=v["note"] or None, payment=v["payment"], hidden=hidden,
        reveal_on=(v["reveal_on"] or None) if hidden else None,
        manual_rate=rate)


def _rate_line(entry: Entry | None) -> str | None:
    """The stored rate and EUR amount of a non-EUR entry (spec section 8)."""
    if entry is None or entry.currency == "EUR" or not entry.fx_rate:
        return None
    return S["fx_line"].format(
        rate=entry.fx_rate.replace(".", ","), currency=entry.currency,
        eur=money.fmt_money(entry.eur_minor, "EUR").removesuffix(" EUR"))


def _form_page(request, s, user, values, status=200, error=None, hints=None,
               needs_rate=False, entry=None):
    ctx = dict(_choices(s, user, entry), values=values, error=error, hints=hints or [],
               needs_rate=needs_rate, entry=entry,
               confirm=values.get("confirm_duplicate") == "1",
               action=f"/entries/{entry.id}" if entry else "/entries",
               is_author=entry is None or entry.created_by == user.id,
               editable=entry is None or visibility.can_edit(
                   user, entry, s.get(Wallet, entry.wallet_id), clock.today()),
               can_reveal=entry is not None and entry.created_by == user.id
               and bool(entry.hidden),
               # A top-up has no edit form, but an adult may undo it:
               # delete_entry removes both halves.
               can_undo=entry is not None and entry.transfer_group is not None
               and user.role == "adult",
               rate_line=_rate_line(entry))
    return _render(request, "entry_detail.html" if entry else "entry_form.html",
                   ctx, status)


# ---------------------------------------------------------------- list

def _row(viewer, e, w, cat_name, author_name, today):
    shown = visibility.present(viewer, e, w, today)
    if shown is None:
        return None
    base = dict(category=cat_name or "", author=author_name,
                date=date_label(e.date), hue=hue(e.category_id))
    if isinstance(shown, visibility.RedactedEntry):
        return dict(base, redacted=True, what=S["redacted_entry"],
                    amount=money.fmt_money(shown.amount_minor, shown.currency),
                    kind=None, url=None, secret=True)
    return dict(base, redacted=False, kind=e.kind,
                what=e.merchant or e.note or cat_name or S["no_name"],
                amount=money.fmt_money(e.amount_minor, e.currency),
                url=f"/entries/{e.id}", secret=visibility.is_secret(e, today))


MAX_ID = 2 ** 53


def _int(value: str | None) -> int | None:
    """A filter id, or None for anything that is not a sane integer."""
    if not value or not value.isdecimal() or not value.isascii():
        return None
    n = int(value)
    return n if n <= MAX_ID else None


@router.get("/entries")
def list_entries(request: Request, month: str | None = None,
                 wallet: str | None = None, category: str | None = None,
                 author: str | None = None, q: str = "",
                 user: User = Depends(require_user)):
    today = clock.today()
    q = q.strip()
    if month is not None and not _MONTH.fullmatch(month):
        month = None
    if month is None and not q:
        month = today[:7]
    conds = [Entry.status == "confirmed", visibility.listable(user, today)]
    if month:
        conds.append(Entry.date.like(f"{month}-%"))
    for col, val in ((Entry.wallet_id, _int(wallet)),
                     (Entry.category_id, _int(category)),
                     (Entry.created_by, _int(author))):
        if val is not None:
            conds.append(col == val)
    if q:
        needle = fold(q)
        conds.append(and_(visibility.text_searchable(user, today), or_(
            func.fold(Entry.merchant).contains(needle, autoescape=True),
            func.fold(Entry.note).contains(needle, autoescape=True))))
    with request.app.state.db.session() as s:
        rows = s.execute(
            select(Entry, Wallet, Category.name, User.name)
            .join(Wallet, Wallet.id == Entry.wallet_id)
            .join(User, User.id == Entry.created_by)
            .outerjoin(Category, Category.id == Entry.category_id)
            .where(*conds).order_by(Entry.date.desc(), Entry.id.desc())
            .limit(LIMIT)).all()
        rows = [r for r in (_row(user, e, w, c, a, today)
                            for e, w, c, a in rows) if r]
        ctx = dict(_choices(s, user), rows=rows, q=q, month=month or "",
                   f_wallet=wallet or "", f_category=category or "",
                   f_author=author or "",
                   authors=[(u.id, u.name) for u in s.scalars(select(User))])
    if month:
        keep = "&" + urlencode({"wallet": wallet or "",
                                "category": category or "",
                                "author": author or "", "q": q})
        ctx.update(
            month_label=f"{month[:4]}. {MONTHS[int(month[5:7]) - 1]}",
            prev_url=f"/entries?month={shift_month(month, -1)}{keep}",
            next_url=(f"/entries?month={shift_month(month, 1)}{keep}"
                      if month < today[:7] else None))
    return _render(request, "entries.html", ctx)


# ---------------------------------------------------------------- create

@router.get("/entries/new")
def new_form(request: Request, user: User = Depends(require_user)):
    with request.app.state.db.session() as s:
        return _form_page(request, s, user, _blank_values(s, user))


@router.post("/entries")
async def create(request: Request, user: User = Depends(require_user)):
    v = await _read(request)
    with request.app.state.db.session() as s:
        try:
            data = _build(v)
            if v["confirm_duplicate"] != "1":
                hints = svc.find_duplicates(s, user, data)
                if hints:
                    return _form_page(request, s, user, v, hints=hints)
            svc.create_entry(s, user, data)
        except svc.NeedsRate:
            return _form_page(request, s, user, v, 422, S["rate_needed"],
                              needs_rate=True)
        except svc.NotAllowed:
            raise HTTPException(status_code=403) from None
        except ValueError as exc:
            return _form_page(request, s, user, v, 422,
                              S.get(str(exc), S["form_invalid"]))
    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------------- one entry

def _in_range(entry_id: int) -> None:
    if not 0 < entry_id <= MAX_ID:
        raise svc.NotAllowed("no such entry")


def _load(s, user, entry_id: int) -> tuple[Entry, Wallet]:
    """The entry in full, or 404: a missing, deleted, redacted or invisible
    entry all look the same."""
    e = s.get(Entry, entry_id) if 0 < entry_id <= MAX_ID else None
    w = s.get(Wallet, e.wallet_id) if e else None
    if e is None or not isinstance(
            visibility.present(user, e, w, clock.today()), Entry):
        raise HTTPException(status_code=404)
    return e, w


@router.get("/entries/{entry_id}")
def detail(request: Request, entry_id: int, user: User = Depends(require_user)):
    with request.app.state.db.session() as s:
        e, w = _load(s, user, entry_id)
        return _form_page(request, s, user, _entry_values(e), entry=e)


@router.post("/entries/{entry_id}")
async def update(request: Request, entry_id: int,
                 user: User = Depends(require_user)):
    v = await _read(request)
    with request.app.state.db.session() as s:
        e, w = _load(s, user, entry_id)
        if e.created_by != user.id:
            # Only the author controls secrecy; keep it as it is.
            v["hidden"] = "1" if e.hidden else ""
            v["reveal_on"] = e.reveal_on or ""
        try:
            svc.update_entry(s, user, entry_id, _build(v))
        except svc.NeedsRate:
            return _form_page(request, s, user, v, 422, S["rate_needed"],
                              needs_rate=True, entry=e)
        except svc.NotAllowed:
            raise HTTPException(status_code=403) from None
        except ValueError as exc:
            return _form_page(request, s, user, v, 422,
                              S.get(str(exc), S["form_invalid"]), entry=e)
    return RedirectResponse(f"/entries/{entry_id}", status_code=303)


@router.post("/entries/{entry_id}/delete")
def delete(request: Request, entry_id: int, user: User = Depends(require_user),
           next_url: str = Form("", alias="next")):
    with request.app.state.db.session() as s:
        try:
            _in_range(entry_id)
            svc.delete_entry(s, user, entry_id)
        except svc.NotAllowed:
            raise HTTPException(status_code=403) from None
    # Only a same-site path: "//host" and "/\\host" would leave the site.
    ok = next_url.startswith("/") and not next_url.startswith(("//", "/\\"))
    return RedirectResponse(next_url if ok else "/entries", status_code=303)


@router.post("/entries/{entry_id}/reveal")
def reveal(request: Request, entry_id: int, user: User = Depends(require_user)):
    with request.app.state.db.session() as s:
        try:
            _in_range(entry_id)
            svc.reveal_entry(s, user, entry_id)
        except svc.NotAllowed:
            raise HTTPException(status_code=403) from None
    return RedirectResponse(f"/entries/{entry_id}", status_code=303)
