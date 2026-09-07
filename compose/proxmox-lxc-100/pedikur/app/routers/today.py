from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app import security
from app.models import User, Visit
from app.services import clients, timeutil, treatments, visits
from app.strings.hu import S

router = APIRouter()

# the walk-in select holds the whole client list, not search's default page
CLIENT_LIMIT = 1000

_ERRORS = frozenset({"visit_needs_treatment", "visit_client_missing",
                     "visit_treatment_missing", "visit_gone", "slot_taken"})


@router.get("/")
def today(request: Request, error: str | None = None,
          user: User = Depends(security.require_user)):
    now = timeutil.local_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with request.app.state.db.session() as s:
        rows = list(s.scalars(
            select(Visit)
            .where(Visit.deleted_at.is_(None),
                   Visit.starts_at >= timeutil.to_utc_iso(start),
                   Visit.starts_at < timeutil.to_utc_iso(start + timedelta(days=1)))
            .order_by(Visit.starts_at)))
        pending = visits.unclosed(s)
        return request.app.state.templates.TemplateResponse(
            request, "today.html",
            {"user": user, "tab": "today", "visits": rows,
             "unclosed": pending, "today": now.date(),
             "clients": clients.search(s, "", limit=CLIENT_LIMIT),
             "treatments": treatments.list_active(s),
             "error": S[error] if error in _ERRORS else None})


@router.post("/walk-in")
def walk_in(request: Request, client_id: int = Form(...),
            treatment_ids: list[int] = Form(default=[]),
            user: User = Depends(security.require_user)):
    """A client who arrives without a booking still gets a Visit row: one
    client session is one Visit, whether it was booked or not."""
    if not treatment_ids:
        return RedirectResponse("/?error=visit_needs_treatment", status_code=303)
    now = timeutil.local_now().replace(second=0, microsecond=0)
    try:
        with request.app.state.db.session() as s:
            try:
                visit = visits.book(s, client_id, now, treatment_ids,
                                    created_by=str(user.id))
            except visits.SlotTaken:
                # A walk-in during another Visit is a real situation, not an
                # error: start it when the conflicting ones are over.
                visit = visits.book(s, client_id, _next_free(s, now, treatment_ids),
                                    treatment_ids, created_by=str(user.id))
            visit_id = visit.id
    except visits.SlotTaken:
        return RedirectResponse("/?error=slot_taken", status_code=303)
    except visits.UnknownTreatment:
        return RedirectResponse("/?error=visit_treatment_missing", status_code=303)
    except (LookupError, ValueError):
        return RedirectResponse("/?error=visit_client_missing", status_code=303)
    return RedirectResponse(f"/visits/{visit_id}/close", status_code=303)


def _next_free(session, now, treatment_ids):
    """The end of the last Visit the walk-in's own window would run into.

    Probing only the current minute is not enough: the conflict can be a Visit
    that has not started yet, and the plan's max() over an empty list of
    running Visits was a 500 in exactly that case.
    """
    minutes = sum(t.duration_min for t in
                  visits._treatments(session, treatment_ids))
    conflicting = visits.overlapping(
        session, timeutil.to_utc_iso(now),
        timeutil.to_utc_iso(timeutil.add_minutes(timeutil.to_utc(now), minutes)))
    if not conflicting:
        return now
    return max(timeutil.from_utc_iso(v.ends_at) for v in conflicting)
