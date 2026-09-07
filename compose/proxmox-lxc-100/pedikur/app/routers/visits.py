from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User, Visit
from app.services import clients, timeutil, treatments, visits
from app.strings.hu import S

router = APIRouter(prefix="/visits")

_ERRORS = frozenset({"visit_slot_taken", "visit_gone", "visit_bad_status",
                     "visit_needs_treatment", "treatment_price_invalid"})

# One practitioner's whole client list fits in a select; search's default of
# 20 would silently hide everyone she registered after the twentieth.
CLIENT_LIMIT = 1000


def _form_page(request: Request, user: User, start: str,
               client_id: int | None, error_key: str | None = None,
               status_code: int = 200):
    with request.app.state.db.session() as s:
        return request.app.state.templates.TemplateResponse(
            request, "visit_form.html",
            {"user": user, "tab": "calendar", "visit": None, "start": start,
             "client_id": client_id,
             "treatments": treatments.list_active(s),
             "clients": clients.search(s, "", limit=CLIENT_LIMIT),
             "error": S[error_key] if error_key else None},
            status_code=status_code)


@router.get("/new")
def new(request: Request, start: str = "", client_id: int | None = None,
        user: User = Depends(security.require_user)):
    """`start` is a local ISO datetime, e.g. 2026-09-10T10:00, from the grid."""
    return _form_page(request, user, start, client_id)


@router.post("/new")
def create(request: Request,
           client_id: int = Form(...),
           start: str = Form(...),
           end: str = Form(""),
           treatment_ids: list[int] = Form(default=[]),
           user: User = Depends(security.require_user)):
    # Form(...) on the list would answer an unticked form with FastAPI's raw
    # 422 JSON body, which is not a page and says nothing she can act on.
    if not treatment_ids:
        return _form_page(request, user, start, client_id,
                          "visit_needs_treatment", status_code=400)
    try:
        # as_local rather than replace(): replace() would discard an offset a
        # crafted POST already carried, and would silently relocate a wall
        # clock time the spring forward skipped.
        starts = timeutil.as_local(datetime.fromisoformat(start))
        ends = timeutil.as_local(datetime.fromisoformat(end)) if end else None
    except ValueError:
        return _form_page(request, user, start, client_id,
                          "visit_time_invalid", status_code=400)

    try:
        with request.app.state.db.session() as s:
            visits.book(s, client_id, starts, treatment_ids,
                        created_by=str(user.id), ends_at_local=ends)
    except visits.SlotTaken:
        return _form_page(request, user, start, client_id,
                          "slot_taken", status_code=409)
    except visits.UnknownTreatment:
        return _form_page(request, user, start, client_id,
                          "visit_treatment_missing", status_code=400)
    except visits.UnknownClient:
        return _form_page(request, user, start, client_id,
                          "visit_client_missing", status_code=400)
    except ValueError:
        return _form_page(request, user, start, client_id,
                          "visit_time_invalid", status_code=400)
    return RedirectResponse(f"/calendar?day={starts.date()}", status_code=303)


@router.get("/{visit_id}/close")
def close_form(request: Request, visit_id: int, error: str | None = None,
               user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        visit = s.get(Visit, visit_id)
        if visit is None:
            return RedirectResponse("/?error=visit_gone", status_code=303)
        return request.app.state.templates.TemplateResponse(
            request, "visit_close.html",
            {"user": user, "tab": "today", "visit": visit,
             "treatments": treatments.list_active(s),
             "error": S[error] if error in _ERRORS else None})


@router.post("/{visit_id}/close")
async def close(request: Request, visit_id: int,
                user: User = Depends(security.require_user)):
    form = await request.form()
    # price_<item id>, in EUR as typed, empty meaning "the price list price"
    overrides: dict[int, int] = {}
    for key, value in form.items():
        if not key.startswith("price_") or not str(value).strip():
            continue
        try:
            overrides[int(key.removeprefix("price_"))] = \
                treatments.parse_price(str(value))
        except ValueError:
            return RedirectResponse(
                f"/visits/{visit_id}/close?error=treatment_price_invalid",
                status_code=303)
    # get without a default: close() reads None as "leave it alone" and "" as
    # "clear it", and a caller that omits the field must not wipe the column.
    findings = form.get("findings")
    note = form.get("note")
    try:
        with request.app.state.db.session() as s:
            visits.close(s, visit_id, price_overrides=overrides,
                         findings=None if findings is None else str(findings),
                         note=None if note is None else str(note))
    except visits.SlotTaken:
        return RedirectResponse(
            f"/visits/{visit_id}/close?error=visit_slot_taken", status_code=303)
    except LookupError:
        return RedirectResponse("/?error=visit_gone", status_code=303)
    return RedirectResponse("/", status_code=303)


@router.post("/{visit_id}/status")
def status(request: Request, visit_id: int, value: str = Form(...),
           user: User = Depends(security.require_user)):
    try:
        with request.app.state.db.session() as s:
            visits.set_status(s, visit_id, value)
    except visits.SlotTaken:
        return RedirectResponse(
            f"/visits/{visit_id}/close?error=visit_slot_taken", status_code=303)
    except ValueError:
        # a status the CHECK constraint would refuse is a broken client, not a
        # Visit that is gone: saying "gone" sends her looking for the wrong thing
        return RedirectResponse(
            f"/visits/{visit_id}/close?error=visit_bad_status", status_code=303)
    except LookupError:
        return RedirectResponse("/?error=visit_gone", status_code=303)
    return RedirectResponse("/", status_code=303)


@router.post("/{visit_id}/treatments")
def add_treatment(request: Request, visit_id: int,
                  treatment_id: int = Form(...),
                  user: User = Depends(security.require_user)):
    # Deliberately not idempotent: two of the same Treatment on one Visit is a
    # real thing. A mis-tap is undone with the remove button below.
    try:
        with request.app.state.db.session() as s:
            visits.add_treatment(s, visit_id, treatment_id)
    except visits.SlotTaken:
        return RedirectResponse(
            f"/visits/{visit_id}/close?error=visit_slot_taken", status_code=303)
    except LookupError:
        return RedirectResponse("/?error=visit_gone", status_code=303)
    except ValueError:
        return RedirectResponse(
            f"/visits/{visit_id}/close?error=visit_needs_treatment",
            status_code=303)
    return RedirectResponse(f"/visits/{visit_id}/close", status_code=303)


@router.post("/{visit_id}/treatments/{item_id}/remove")
def remove_treatment(request: Request, visit_id: int, item_id: int,
                     user: User = Depends(security.require_user)):
    try:
        with request.app.state.db.session() as s:
            visits.remove_treatment(s, visit_id, item_id)
    except LookupError:
        return RedirectResponse("/?error=visit_gone", status_code=303)
    except ValueError:
        return RedirectResponse(
            f"/visits/{visit_id}/close?error=visit_needs_treatment",
            status_code=303)
    return RedirectResponse(f"/visits/{visit_id}/close", status_code=303)
