import re

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app import security
from app.models import User, WorkingHours
from app.services import treatments
from app.strings.hu import S

router = APIRouter(prefix="/settings")

# A whitelist, not a bare S lookup: the value comes from the query string, so
# S.get(error) would let ?error=weekdays render the repr of a Python list, and
# ?error=nav_calendar render "Naptar" as if it were a failure.
_ERRORS = frozenset({
    "treatment_price_invalid", "treatment_duration_invalid",
    "treatment_name_required", "treatment_name_taken",
    "hours_end_before_start", "hours_time_invalid",
})

HHMM = re.compile(r"^([01][0-9]|2[0-3]):[0-5][0-9]$")


def _error(key: str | None, day: int | None = None) -> str | None:
    if key not in _ERRORS:
        return None
    text = S[key]
    if day is not None and 0 <= day <= 6:
        text += S["weekdays"][day]
    return text


def _render(request: Request, name: str, context: dict):
    return request.app.state.templates.TemplateResponse(request, name, context)


@router.get("")
def index(request: Request, user: User = Depends(security.require_user)):
    return _render(request, "settings_index.html", {"user": user, "tab": "more"})


@router.get("/treatments")
def treatment_list(request: Request, error: str | None = None,
                   user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = treatments.list_all(s)
        return _render(request, "settings_treatments.html",
                       {"user": user, "tab": "more", "treatments": rows,
                        "error": _error(error)})


@router.post("/treatments")
def treatment_create(request: Request,
                     name: str = Form(...),
                     duration_min: str = Form(...),
                     price_eur: str = Form(...),
                     user: User = Depends(security.require_user)):
    # Bad input redirects back with a message. Letting ValueError escape would
    # be a 500 on a mistyped price, which is the most likely typo on this form.
    try:
        cents = treatments.parse_price(price_eur)
    except ValueError:
        return RedirectResponse(
            "/settings/treatments?error=treatment_price_invalid", status_code=303)
    try:
        minutes = int(duration_min)
    except ValueError:
        minutes = 0
    if minutes < 5:
        return RedirectResponse(
            "/settings/treatments?error=treatment_duration_invalid", status_code=303)
    try:
        with request.app.state.db.session() as s:
            treatments.create(s, name, minutes, cents, created_by=str(user.id))
    except ValueError as exc:
        key = ("treatment_name_taken" if "already exists" in str(exc)
               else "treatment_name_required")
        return RedirectResponse(f"/settings/treatments?error={key}",
                                status_code=303)
    return RedirectResponse("/settings/treatments", status_code=303)


@router.post("/treatments/{treatment_id}/deactivate")
def treatment_deactivate(request: Request, treatment_id: int,
                         user: User = Depends(security.require_user)):
    _toggle(request, treatment_id, treatments.deactivate)
    return RedirectResponse("/settings/treatments", status_code=303)


@router.post("/treatments/{treatment_id}/activate")
def treatment_activate(request: Request, treatment_id: int,
                       user: User = Depends(security.require_user)):
    _toggle(request, treatment_id, treatments.activate)
    return RedirectResponse("/settings/treatments", status_code=303)


def _toggle(request: Request, treatment_id: int, action) -> None:
    """A missing id is a stale page, not a server fault: the list simply
    reloads without it rather than showing a stack trace."""
    try:
        with request.app.state.db.session() as s:
            action(s, treatment_id)
    except LookupError:
        pass


@router.get("/hours")
def hours_form(request: Request, error: str | None = None,
               day: int | None = None, saved: int = 0,
               user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = {r.weekday: r for r in s.scalars(
            select(WorkingHours).where(WorkingHours.weekday.isnot(None)))}
        return _render(request, "settings_hours.html",
                       {"user": user, "tab": "more", "rows": rows,
                        "weekdays": list(enumerate(S["weekdays"])),
                        "error": _error(error, day), "saved": saved})


@router.post("/hours")
async def hours_save(request: Request,
                     user: User = Depends(security.require_user)):
    form = await request.form()
    days = []
    for weekday in range(7):
        closed = form.get(f"closed_{weekday}") is not None
        start = form.get(f"start_{weekday}") or "09:00"
        end = form.get(f"end_{weekday}") or "17:00"
        # The schema's CHECK is the only other guard, and it fires at commit
        # inside the session, so anything but HH:MM would be an IntegrityError
        # escaping this route as a 500. A browser without a native time input
        # sends a plain text field.
        if not (HHMM.match(start) and HHMM.match(end)):
            return RedirectResponse(
                f"/settings/hours?error=hours_time_invalid&day={weekday}",
                status_code=303)
        # An open day whose close is not after its open produces an empty or
        # inverted calendar column, and nothing downstream would say why.
        if not closed and end <= start:
            return RedirectResponse(
                f"/settings/hours?error=hours_end_before_start&day={weekday}",
                status_code=303)
        days.append((weekday, start, end, closed))

    # Every day is validated before a session opens, so a refused save writes
    # nothing at all rather than the days that came before the bad one.
    with request.app.state.db.session() as s:
        for weekday, start, end, closed in days:
            row = s.scalars(select(WorkingHours)
                            .where(WorkingHours.weekday == weekday)).one_or_none()
            if row is None:
                s.add(WorkingHours(weekday=weekday, start=start, end=end,
                                   is_closed=int(closed)))
            else:
                row.start, row.end, row.is_closed = start, end, int(closed)
    return RedirectResponse("/settings/hours?saved=1", status_code=303)
