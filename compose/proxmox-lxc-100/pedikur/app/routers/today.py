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
                     "visit_treatment_missing", "visit_gone", "slot_taken",
                     "visit_time_invalid"})


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
            # A walk-in during another Visit is a real situation, not an error:
            # it starts when the ones it would run into are over. book() raises
            # before it adds anything, so nothing is pending on the session
            # when the search runs.
            visit = visits.book(s, client_id, _next_free(s, now, treatment_ids),
                                treatment_ids, created_by=str(user.id))
            # Immediately done, per spec section 5: the client is standing
            # there. Leaving it planned means one interruption puts her on the
            # unclosed banner and, because the interval counts done Visits
            # only, on the Recall List weeks early.
            visits.close(s, visit.id)
            visit_id = visit.id
    except visits.SlotTaken:
        return RedirectResponse("/?error=slot_taken", status_code=303)
    except visits.UnknownTreatment:
        return RedirectResponse("/?error=visit_treatment_missing", status_code=303)
    except LookupError:
        return RedirectResponse("/?error=visit_client_missing", status_code=303)
    except ValueError:
        return RedirectResponse("/?error=visit_time_invalid", status_code=303)
    return RedirectResponse(f"/visits/{visit_id}/close", status_code=303)


MAX_HOPS = 20


def _next_free(session, now, treatment_ids):
    """The first moment the walk-in's own window fits.

    One hop is not enough. Two back to back bookings, 10:00-10:45 and
    10:45-11:30, and a 45 minute walk-in at 10:00: the probe window
    [10:00, 10:45) is half open, so only the first is found, the walk-in is
    moved to 10:45, and it lands exactly on the second. Back to back is the
    normal shape of her day, so the fallback has to keep walking.

    Compared as UTC strings, not as local datetimes: two aware datetimes that
    share a tzinfo are compared by their wall clock fields, so on the autumn
    changeover an end of 02:30 CEST would beat an end of 02:10 CET while being
    forty minutes earlier in real time.
    """
    minutes = sum(t.duration_min for t in
                  visits._treatments(session, treatment_ids))
    start = timeutil.to_utc(now)
    for _ in range(MAX_HOPS):
        start_iso = timeutil.to_utc_iso(start)
        end_iso = timeutil.to_utc_iso(timeutil.add_minutes(start, minutes))
        conflicting = visits.overlapping(session, start_iso, end_iso)
        if not conflicting:
            return start
        # strictly later every hop, so this terminates
        start = timeutil.to_utc(
            timeutil.from_utc_iso(max(v.ends_at for v in conflicting)))
    return start
