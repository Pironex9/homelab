from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from app import money
from app.clock import now_utc
from app.models import Category, Recurring, User
from app.routers import entries as er
from app.security import require_adult
from app.strings.hu import S

router = APIRouter()

KINDS = ("expense", "income")
# top_up looks these two up by name, so they keep it.
LOCKED = {("Zsebpénz", "expense"), ("Egyéb bevétel", "income")}
SORT_MAX = 9999


class Invalid(Exception):
    """A string key to show."""


def _eur_text(minor: int | None) -> str:
    return "" if minor is None else er._amount_text(minor)


def _page(request, s, user, status=200, error=None, where=None, values=None):
    cats = s.scalars(select(Category).order_by(
        Category.kind, Category.sort, Category.id)).all()
    cat_rows = [dict(id=c.id, name=c.name, kind=c.kind, sort=str(c.sort),
                     limit=_eur_text(c.monthly_limit_eur_minor),
                     archived=c.archived_at is not None,
                     locked=(c.name, c.kind) in LOCKED) for c in cats]
    rec = s.scalars(select(Recurring).where(
        Recurring.archived_at.is_(None)).order_by(Recurring.id)).all()
    rec_rows = [dict(id=r.id, name=r.name, kind=r.kind,
                     category_id=str(r.category_id),
                     amount=er._amount_text(r.amount_minor),
                     currency=r.currency, day=str(r.day_of_month),
                     owner_user_id=str(r.owner_user_id or "")) for r in rec]
    if where and values is not None:
        # Show what was typed in the form that failed, not the stored values.
        for row in cat_rows + rec_rows:
            if where == f"{'cat' if 'limit' in row else 'rec'}-{row['id']}":
                row.update(values)
    ctx = dict(categories=cat_rows, recurring=rec_rows, error=error,
               error_in=where, values=values or {},
               currencies=er.CURRENCIES, kinds=KINDS,
               adults=[(u.id, u.name) for u in s.scalars(
                   select(User).where(User.role == "adult").order_by(User.id))],
               active_cats=[(c.id, c.name, c.kind) for c in cats
                            if c.archived_at is None])
    return er._render(request, "settings.html", ctx, status)


def _fail(request, s, user, where, values, exc):
    key = str(exc)
    return _page(request, s, user, 422, S.get(key, S["form_invalid"]),
                 where, values)


async def _read(request: Request, keys) -> dict:
    f = await request.form()
    return {k: str(f.get(k, "")).strip() for k in keys}


def _sort(v: dict) -> int:
    text = v["sort"] or "0"
    if not text.isascii() or not text.isdecimal() or int(text) > SORT_MAX:
        raise Invalid("e_sort")
    return int(text)


def _name(s, v: dict, kind: str, own_id: int | None = None) -> str:
    name = v["name"]
    if not name or len(name) > 60:
        raise Invalid("e_name")
    clash = s.scalars(select(Category.id).where(
        func.fold(Category.name) == er.fold(name), Category.kind == kind,
        Category.id != (own_id or 0))).first()
    if clash is not None:
        raise Invalid("e_name_taken")
    return name


def _category(s, cid: int) -> Category:
    c = s.get(Category, cid) if 0 < cid <= er.MAX_ID else None
    if c is None:
        raise HTTPException(status_code=404)
    return c


@router.get("/settings")
def settings(request: Request, user: User = Depends(require_adult)):
    with request.app.state.db.session() as s:
        return _page(request, s, user)


@router.post("/settings/categories")
async def add_category(request: Request, user: User = Depends(require_adult)):
    v = await _read(request, ("name", "kind", "sort"))
    with request.app.state.db.session() as s:
        try:
            if v["kind"] not in KINDS:
                raise Invalid("form_invalid")
            s.add(Category(name=_name(s, v, v["kind"]), kind=v["kind"],
                           sort=_sort(v)))
        except Invalid as exc:
            return _fail(request, s, user, "cat-new", v, exc)
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/categories/{cid}")
async def edit_category(request: Request, cid: int,
                        user: User = Depends(require_adult)):
    v = await _read(request, ("name", "limit", "sort"))
    with request.app.state.db.session() as s:
        c = _category(s, cid)
        try:
            name = _name(s, v, c.kind, c.id)
            if (c.name, c.kind) in LOCKED and name != c.name:
                raise Invalid("e_name_locked")
            limit = None
            if v["limit"]:
                try:
                    limit = money.parse_amount(v["limit"])
                except ValueError:
                    raise Invalid("amount_invalid") from None
            c.name, c.monthly_limit_eur_minor, c.sort = name, limit, _sort(v)
        except Invalid as exc:
            s.rollback()
            return _fail(request, s, user, f"cat-{cid}", v, exc)
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/categories/{cid}/archive")
def archive_category(request: Request, cid: int,
                     user: User = Depends(require_adult)):
    with request.app.state.db.session() as s:
        c = _category(s, cid)
        c.archived_at = None if c.archived_at else now_utc()
    return RedirectResponse("/settings", status_code=303)


# ---------------------------------------------------------------- recurring

REC_KEYS = ("name", "kind", "category_id", "amount", "currency", "day",
            "owner_user_id")


def _recurring_fields(s, v: dict, keep_category: int | None = None) -> dict:
    if not v["name"] or len(v["name"]) > 60:
        raise Invalid("e_name")
    if v["kind"] not in KINDS:
        raise Invalid("form_invalid")
    cid = er._int(v["category_id"])
    c = s.get(Category, cid) if cid else None
    if c is None or (c.archived_at is not None and c.id != keep_category):
        raise Invalid("category_required")
    if c.kind != v["kind"]:
        raise Invalid("e_category_kind")
    try:
        amount = money.parse_amount(v["amount"])
    except ValueError:
        raise Invalid("amount_invalid") from None
    if v["currency"].upper() not in er.CURRENCIES:
        raise Invalid("e_currency")
    if not (v["day"].isascii() and v["day"].isdecimal()
            and 1 <= int(v["day"]) <= 31):
        raise Invalid("e_day")
    owner = None
    if v["owner_user_id"]:
        oid = er._int(v["owner_user_id"])
        u = s.get(User, oid) if oid else None
        if u is None or u.role != "adult":
            raise Invalid("e_owner")
        owner = u.id
    return dict(name=v["name"], kind=v["kind"], category_id=c.id,
                amount_minor=amount, currency=v["currency"].upper(),
                day_of_month=int(v["day"]), owner_user_id=owner)


@router.post("/settings/recurring")
async def add_recurring(request: Request, user: User = Depends(require_adult)):
    v = await _read(request, REC_KEYS)
    with request.app.state.db.session() as s:
        try:
            s.add(Recurring(**_recurring_fields(s, v)))
        except Invalid as exc:
            return _fail(request, s, user, "rec-new", v, exc)
    return RedirectResponse("/settings", status_code=303)


def _recurring(s, rid: int) -> Recurring:
    r = s.get(Recurring, rid) if 0 < rid <= er.MAX_ID else None
    if r is None or r.archived_at is not None:
        raise HTTPException(status_code=404)
    return r


@router.post("/settings/recurring/{rid}")
async def edit_recurring(request: Request, rid: int,
                         user: User = Depends(require_adult)):
    v = await _read(request, REC_KEYS)
    with request.app.state.db.session() as s:
        r = _recurring(s, rid)
        try:
            for k, val in _recurring_fields(s, v, r.category_id).items():
                setattr(r, k, val)
        except Invalid as exc:
            s.rollback()
            return _fail(request, s, user, f"rec-{rid}", v, exc)
    return RedirectResponse("/settings", status_code=303)


@router.post("/settings/recurring/{rid}/archive")
def archive_recurring(request: Request, rid: int,
                      user: User = Depends(require_adult)):
    with request.app.state.db.session() as s:
        _recurring(s, rid).archived_at = now_utc()
    return RedirectResponse("/settings", status_code=303)
