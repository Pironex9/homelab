"""The manual capture form as an offline-capable page, and the endpoint its
queue (static/capture.js) uploads to.

The page is cached by the service worker, so what it renders is what the
person sees on a dead connection: the last categories and wallets seen online.
"""
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.models import Entry, User, Wallet
from app.routers import entries as er
from app.security import require_user, require_user_json
from app.services import entries as svc
from app.strings.hu import S

router = APIRouter()

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_FIELDS = ("kind", "amount", "currency", "date", "merchant", "note",
           "category_id", "payment", "wallet_id", "hidden", "reveal_on",
           "manual_rate")


@router.get("/capture")
def capture_page(request: Request, user: User = Depends(require_user)):
    with request.app.state.db.session() as s:
        ctx = dict(er._choices(s, user), values=er._blank_values(s, user),
                   error=None, hints=[], needs_rate=False, entry=None,
                   confirm=False, is_author=True, user_id=user.id)
    return request.app.state.templates.TemplateResponse(
        request, "capture.html", ctx)


def _answer(code: int, client_uuid, **extra) -> JSONResponse:
    return JSONResponse(dict(client_uuid=client_uuid, **extra),
                        status_code=code)


def _text(value) -> str:
    # JSON may carry numbers or nulls; the form path only ever has text.
    return "" if value is None else str(value).strip()


@router.post("/capture/sync")
async def sync(request: Request, user: User = Depends(require_user_json)):
    """One queued capture. The client removes it from its queue only on a 2xx
    JSON answer that echoes its client_uuid, so every refusal echoes it too
    and says why; the item then stays queued for the person to fix."""
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        body = None
    if not isinstance(body, dict):
        return _answer(422, None, error=S["form_invalid"])
    uid = body.get("client_uuid")
    if not isinstance(uid, str) or not _UUID.fullmatch(uid):
        return _answer(422, uid if isinstance(uid, str) else None,
                       error=S["form_invalid"])
    # The cached form names the user it was rendered for. An item queued by
    # someone who has since logged out waits for them: uploading it under the
    # current session would make it this user's entry, secret or not.
    queued_by = body.get("user_id")
    if queued_by is not None and _text(queued_by) != str(user.id):
        return _answer(409, uid, error=S["queue_other_user"])
    v = {k: _text(body.get(k)) for k in _FIELDS}
    with request.app.state.db.session() as s:
        existing = s.scalar(select(Entry).where(Entry.client_uuid == uid))
        if existing is not None:
            # A retry after a lost response: the same answer as the first time.
            # Checked before the duplicate search, which would otherwise find
            # the first upload and turn the retry into a second entry.
            if existing.created_by != user.id:
                return _answer(409, uid, error=S["queue_other_user"])
            return _answer(200, uid, entry_id=existing.id,
                           status=existing.status)
        try:
            data = er._build(v)
            data.client_uuid = uid
            status = "confirmed"
            # The person could not see a duplicate prompt offline, so a likely
            # duplicate waits under /drafts instead. /drafts shows household
            # drafts only, so elsewhere a draft would be lost from sight.
            if svc.find_duplicates(s, user, data):
                wallet = s.get(Wallet, data.wallet_id)
                if wallet is not None and wallet.owner_user_id is None:
                    status = "draft"
            e = svc.create_entry(s, user, data, status=status)
        except svc.NeedsRate:
            return _answer(422, uid, error=S["rate_needed"], needs_rate=True)
        except svc.NotAllowed:
            return _answer(403, uid, error=S["form_invalid"])
        except ValueError as exc:
            return _answer(422, uid, error=S.get(str(exc), S["form_invalid"]))
        return _answer(200, uid, entry_id=e.id, status=e.status)
