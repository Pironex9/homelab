from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request

from app import security
from app.models import User
from app.services import schedule, timeutil
from app.strings.hu import S

router = APIRouter(prefix="/calendar")


@router.get("")
def week(request: Request, day: str = "",
         user: User = Depends(security.require_user)):
    try:
        anchor = date.fromisoformat(day) if day else timeutil.local_now().date()
    except ValueError:
        # a hand-edited or stale query string is a bad link, not a server fault
        anchor = timeutil.local_now().date()
    monday = anchor - timedelta(days=anchor.weekday())
    with request.app.state.db.session() as s:
        grid = schedule.week_grid(s, monday)
        return request.app.state.templates.TemplateResponse(
            request, "week.html",
            {"user": user, "tab": "calendar", "grid": grid,
             "prev": (monday - timedelta(days=7)).isoformat(),
             "next": (monday + timedelta(days=7)).isoformat(),
             "today": timeutil.local_now().date(),
             "day_names": S["weekdays_short"],
             "slot_min": schedule.SLOT_MIN})
