from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app import money
from app.models import Category, Entry, User, Wallet
from app.routers import entries as er
from app.security import require_adult
from app.services import entries as svc, recurring
from app.services.home import date_label, hue
from app.strings.hu import S

router = APIRouter()


def _drafts(s):
    household = s.scalars(select(Wallet).where(
        Wallet.owner_user_id.is_(None))).one()
    return (Entry.status == "draft", Entry.deleted_at.is_(None),
            Entry.wallet_id == household.id)


def _load(s, entry_id: int) -> Entry:
    e = s.scalars(select(Entry).where(
        Entry.id == entry_id, *_drafts(s))).one_or_none() \
        if 0 < entry_id <= er.MAX_ID else None
    if e is None:
        raise HTTPException(status_code=404)
    return e


def _page(request, s, user, e, values, status=200, error=None,
          needs_rate=False):
    ctx = dict(er._choices(s, user, e), values=values, error=error,
               needs_rate=needs_rate, confirm=False, entry=e,
               action=f"/drafts/{e.id}/confirm", hints=[],
               is_author=e.created_by == user.id)
    return er._render(request, "draft_confirm.html", ctx, status)


@router.get("/drafts")
def list_drafts(request: Request, user: User = Depends(require_adult)):
    with request.app.state.db.session() as s:
        rows = s.execute(
            select(Entry, Category.name)
            .outerjoin(Category, Category.id == Entry.category_id)
            .where(*_drafts(s)).order_by(Entry.date, Entry.id)).all()
        ctx = dict(rows=[dict(
            what=e.merchant or e.note or cname or S["no_name"],
            amount=money.fmt_money(e.amount_minor, e.currency), kind=e.kind,
            meta=f"{cname or ''} · {date_label(e.date)}".strip(" ·"),
            hue=hue(e.category_id), url=f"/drafts/{e.id}")
            for e, cname in rows])
    return er._render(request, "drafts.html", ctx)


@router.get("/drafts/{entry_id}")
def draft_form(request: Request, entry_id: int,
               user: User = Depends(require_adult)):
    with request.app.state.db.session() as s:
        e = _load(s, entry_id)
        return _page(request, s, user, e, er._entry_values(e))


@router.post("/drafts/{entry_id}/confirm")
async def confirm(request: Request, entry_id: int,
                  user: User = Depends(require_adult)):
    v = await er._read(request)
    with request.app.state.db.session() as s:
        e = _load(s, entry_id)
        try:
            recurring.confirm_draft(s, user, entry_id, er._build(v))
        except svc.NeedsRate:
            return _page(request, s, user, e, v, 422, S["rate_needed"],
                         needs_rate=True)
        except svc.NotAllowed:
            raise HTTPException(status_code=403) from None
        except ValueError as exc:
            return _page(request, s, user, e, v, 422,
                         S.get(str(exc), S["form_invalid"]))
    return RedirectResponse("/drafts", status_code=303)
