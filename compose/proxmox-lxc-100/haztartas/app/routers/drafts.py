from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app import money
from app import clock
from app.models import Category, Entry, User, Wallet
from app.routers import entries as er
from app.security import require_adult
from app.services import entries as svc, recurring, visibility
from app.services.home import date_label, hue
from app.strings.hu import S

router = APIRouter()


def _drafts(s):
    household = s.scalars(select(Wallet).where(
        Wallet.owner_user_id.is_(None))).one()
    return (Entry.status == "draft", Entry.deleted_at.is_(None),
            Entry.wallet_id == household.id)


def _load(s, user: User, entry_id: int) -> Entry:
    e = s.scalars(select(Entry).where(
        Entry.id == entry_id, *_drafts(s))).one_or_none() \
        if 0 < entry_id <= er.MAX_ID else None
    # A secret draft of the other adult is not yours to open or confirm.
    if e is None or not visibility.can_edit(
            user, e, s.get(Wallet, e.wallet_id), clock.today()):
        raise HTTPException(status_code=404)
    return e


def _page(request, s, user, e, values, status=200, error=None,
          needs_rate=False):
    ctx = dict(er._choices(s, user, e), values=values, error=error,
               needs_rate=needs_rate, confirm=False, entry=e,
               action=f"/drafts/{e.id}/confirm", hints=[],
               is_author=e.created_by == user.id,
               rate_line=er._rate_line(e))
    return er._render(request, "draft_confirm.html", ctx, status)


@router.get("/drafts")
def list_drafts(request: Request, user: User = Depends(require_adult)):
    with request.app.state.db.session() as s:
        today = clock.today()
        household = s.get(Wallet, s.scalars(select(Wallet.id).where(
            Wallet.owner_user_id.is_(None))).one())
        rows = s.execute(
            select(Entry, Category.name, User.name)
            .outerjoin(Category, Category.id == Entry.category_id)
            .join(User, User.id == Entry.created_by)
            .where(*_drafts(s)).order_by(Entry.date, Entry.id)).all()
        out = []
        for e, cname, author in rows:
            shown = visibility.present(user, e, household, today)
            if shown is None:
                continue
            meta = f"{cname or ''} · {date_label(e.date)}".strip(" ·")
            if isinstance(shown, visibility.RedactedEntry):
                out.append(dict(
                    what=S["redacted_entry"], kind=None, url=None,
                    amount=money.fmt_money(e.amount_minor, e.currency),
                    meta=f"{meta} · {author}", hue=hue(e.category_id)))
            else:
                out.append(dict(
                    what=e.merchant or e.note or cname or S["no_name"],
                    amount=money.fmt_money(e.amount_minor, e.currency),
                    kind=e.kind, meta=meta, hue=hue(e.category_id),
                    url=f"/drafts/{e.id}"))
        ctx = dict(rows=out)
    return er._render(request, "drafts.html", ctx)


@router.get("/drafts/{entry_id}")
def draft_form(request: Request, entry_id: int,
               user: User = Depends(require_adult)):
    with request.app.state.db.session() as s:
        e = _load(s, user, entry_id)
        return _page(request, s, user, e, er._entry_values(e))


@router.post("/drafts/{entry_id}/confirm")
async def confirm(request: Request, entry_id: int,
                  user: User = Depends(require_adult)):
    v = await er._read(request)
    with request.app.state.db.session() as s:
        e = _load(s, user, entry_id)
        v["wallet_id"] = str(e.wallet_id)   # a confirm never moves a draft
        if e.created_by != user.id:
            # Only the author controls secrecy; keep it as it is (the form
            # shows no secrecy fields to anyone else).
            v["hidden"] = "1" if e.hidden else ""
            v["reveal_on"] = e.reveal_on or ""
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
