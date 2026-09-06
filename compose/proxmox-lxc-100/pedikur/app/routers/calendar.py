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
    today = timeutil.local_now().date()
    try:
        anchor = date.fromisoformat(day) if day else today
        monday = anchor - timedelta(days=anchor.weekday())
        # date's range ends at 9999-12-31, so the prev/next arithmetic has to
        # be inside the guard too: ?day=9999-12-31 parses and then overflows.
        prev_monday = monday - timedelta(days=7)
        next_monday = monday + timedelta(days=7)
    except (ValueError, OverflowError):
        # a hand-edited or stale query string is a bad link, not a server fault
        monday = today - timedelta(days=today.weekday())
        prev_monday = monday - timedelta(days=7)
        next_monday = monday + timedelta(days=7)
    with request.app.state.db.session() as s:
        grid = schedule.week_grid(s, monday)
        return request.app.state.templates.TemplateResponse(
            request, "week.html",
            {"user": user, "tab": "calendar", "grid": grid,
             "prev": prev_monday.isoformat(),
             "next": next_monday.isoformat(),
             "today": today,
             "day_names": S["weekdays_short"],
             "slot_min": schedule.SLOT_MIN})
