from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app import clock, money
from app.models import Category, Entry, User, Wallet
from app.routers import entries as er
from app.security import require_adult, require_user
from app.services import entries as svc, summary, visibility
from app.services.home import date_label, hue
from app.strings.hu import S

router = APIRouter()
LIMIT = 50


def _children(s):
    return s.execute(
        select(Wallet, User).join(User, User.id == Wallet.owner_user_id)
        .where(User.role == "child").order_by(Wallet.id)).all()


def _wallet_view(s, viewer, wallet, owner, today):
    rows = s.execute(
        select(Entry, Category.name)
        .outerjoin(Category, Category.id == Entry.category_id)
        .where(Entry.wallet_id == wallet.id, Entry.status == "confirmed",
               visibility.listable(viewer, today))
        .order_by(Entry.date.desc(), Entry.id.desc()).limit(LIMIT)).all()
    authors = dict(s.execute(select(User.id, User.name)).all())
    items = []
    for e, cname in rows:
        shown = visibility.present(viewer, e, wallet, today)
        if shown is None:
            continue
        redacted = isinstance(shown, visibility.RedactedEntry)
        items.append(dict(
            what=S["redacted_entry"] if redacted else
            (e.merchant or e.note or cname or S["no_name"]),
            kind=None if redacted else e.kind,
            amount=money.fmt_money(e.amount_minor, e.currency),
            meta=(f"{cname or ''} · {date_label(e.date)}".strip(" ·")
                  + (f" · {authors[e.created_by]}" if redacted else "")),
            hue=hue(e.category_id)))
    return dict(wallet_id=wallet.id, name=owner.name, rows=items,
                balance_minor=summary.wallet_balance(
                    s, wallet.id, viewer, today))


def _page(request, s, user, status=200, error=None, values=None, where=None):
    today = clock.today()
    if user.role == "adult":
        pairs = _children(s)
    else:
        pairs = [(w, user) for w in s.scalars(select(Wallet).where(
            Wallet.owner_user_id == user.id))]
    ctx = dict(
        wallets=[_wallet_view(s, user, w, o, today) for w, o in pairs],
        adult=user.role == "adult", error=error, error_in=where,
        values=values or dict(wallet_id="", amount="", currency="EUR",
                              date=today),
        currencies=er.CURRENCIES)
    return er._render(request, "pocket.html", ctx, status)


@router.get("/pocket")
def pocket(request: Request, user: User = Depends(require_user)):
    with request.app.state.db.session() as s:
        return _page(request, s, user)


def _read(request_form) -> dict:
    return {k: str(request_form.get(k, "")).strip()
            for k in ("wallet_id", "amount", "currency", "date")}


def _child(s, v):
    wid = er._int(v["wallet_id"])
    for w, o in _children(s):
        if w.id == wid:
            return w, o
    raise ValueError("pocket_child_invalid")


@router.post("/pocket/topup")
async def topup(request: Request, user: User = Depends(require_adult)):
    v = _read(await request.form())
    with request.app.state.db.session() as s:
        try:
            w, o = _child(s, v)
            amount = _amount(v)
            svc.top_up(s, user, w.id, amount, v["currency"].upper(), v["date"],
                       note=S["pocket_topup_note"].format(name=o.name))
        except svc.NeedsRate:
            return _page(request, s, user, 422, S["rate_needed"], v, "topup")
        except svc.NotAllowed:
            raise HTTPException(status_code=403) from None
        except ValueError as exc:
            return _page(request, s, user, 422,
                         S.get(str(exc), S["form_invalid"]), v, "topup")
    return RedirectResponse("/pocket", status_code=303)


def _amount(v: dict) -> int:
    try:
        return money.parse_amount(v["amount"])
    except ValueError:
        raise ValueError("amount_invalid") from None


@router.post("/pocket/opening")
async def opening(request: Request, user: User = Depends(require_adult)):
    v = _read(await request.form())
    with request.app.state.db.session() as s:
        try:
            w, _ = _child(s, v)
            data = svc.EntryInput(
                wallet_id=w.id, kind="income", date=v["date"],
                amount_minor=_amount(v), currency=v["currency"].upper(),
                category_id=s.scalars(select(Category.id).where(
                    Category.name == "Egyéb bevétel",
                    Category.kind == "income")).one(),
                merchant=None, note=S["pocket_opening_note"], payment="cash",
                hidden=False, reveal_on=None)
            svc.create_entry(s, user, data)
        except svc.NeedsRate:
            return _page(request, s, user, 422, S["rate_needed"], v, "opening")
        except svc.NotAllowed:
            raise HTTPException(status_code=403) from None
        except ValueError as exc:
            return _page(request, s, user, 422,
                         S.get(str(exc), S["form_invalid"]), v, "opening")
    return RedirectResponse("/pocket", status_code=303)
