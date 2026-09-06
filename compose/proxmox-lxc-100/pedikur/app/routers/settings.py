from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User, WorkingHours
from app.services import treatments
from app.strings.hu import S

router = APIRouter(prefix="/settings")


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
                        "error": S.get(error) if error else None})


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
    except ValueError:
        return RedirectResponse(
            "/settings/treatments?error=treatment_name_required", status_code=303)
    return RedirectResponse("/settings/treatments", status_code=303)


@router.post("/treatments/{treatment_id}/deactivate")
def treatment_deactivate(request: Request, treatment_id: int,
                         user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        treatments.deactivate(s, treatment_id)
    return RedirectResponse("/settings/treatments", status_code=303)


@router.post("/treatments/{treatment_id}/activate")
def treatment_activate(request: Request, treatment_id: int,
                       user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        treatments.activate(s, treatment_id)
    return RedirectResponse("/settings/treatments", status_code=303)


@router.get("/hours")
def hours_form(request: Request, error: str | None = None,
               user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = {r.weekday: r for r in s.query(WorkingHours)
                .filter(WorkingHours.weekday.isnot(None))}
        return _render(request, "settings_hours.html",
                       {"user": user, "tab": "more", "rows": rows,
                        "weekdays": list(enumerate(S["weekdays"])),
                        "error": error})


@router.post("/hours")
async def hours_save(request: Request,
                     user: User = Depends(security.require_user)):
    form = await request.form()
    days = []
    for weekday in range(7):
        closed = form.get(f"closed_{weekday}") is not None
        start = form.get(f"start_{weekday}") or "09:00"
        end = form.get(f"end_{weekday}") or "17:00"
        # An open day whose close is not after its open produces an empty or
        # inverted calendar column, and nothing downstream would say why.
        if not closed and end <= start:
            return RedirectResponse(
                "/settings/hours?error=" + S["hours_end_before_start"]
                + S["weekdays"][weekday], status_code=303)
        days.append((weekday, start, end, closed))

    with request.app.state.db.session() as s:
        for weekday, start, end, closed in days:
            row = s.query(WorkingHours).filter_by(weekday=weekday).one_or_none()
            if row is None:
                s.add(WorkingHours(weekday=weekday, start=start, end=end,
                                   is_closed=int(closed)))
            else:
                row.start, row.end, row.is_closed = start, end, int(closed)
    return RedirectResponse("/settings/hours", status_code=303)
