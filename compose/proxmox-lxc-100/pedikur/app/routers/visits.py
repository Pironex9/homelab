from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.services import clients, timeutil, treatments, visits
from app.strings.hu import S

router = APIRouter(prefix="/visits")

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
