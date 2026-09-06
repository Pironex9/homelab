"""Working hours to a renderable week grid.

Phase 1 renders her own Visits only. Google busy blocks, buffers and free-slot
highlighting arrive in phase 3 and extend this module rather than replacing it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Visit, WorkingHours
from app.services import timeutil

SLOT_MIN = 15
FALLBACK_OPEN_MIN = 8 * 60
FALLBACK_CLOSE_MIN = 18 * 60
DAY_END_MIN = 24 * 60
# planned and done are what the overlap check treats as busy. no_show is drawn
# as well, greyed: a day where nobody turned up would otherwise render as if
# nothing had ever been booked, and she still has to be able to reach the row.
DRAWN_STATUSES = ("planned", "done", "no_show")


@dataclass(frozen=True)
class DayHours:
    open_min: int
    close_min: int
    is_closed: bool


@dataclass(frozen=True)
class VisitBlock:
    visit_id: int
    client_name: str
    has_alert: bool
    label: str
    status: str
    starts_at: str
    ends_at: str
    row_start: int
    row_span: int


@dataclass(frozen=True)
class DayColumn:
    date: date
    is_closed: bool
    open_min: int
    close_min: int
    blocks: list[VisitBlock]


@dataclass(frozen=True)
class WeekGrid:
    monday: date
    start_min: int
    end_min: int
    rows: int
    days: list[DayColumn]


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def hours_for(session: Session, day: date) -> DayHours | None:
    """A date row overrides the weekday default. None means no hours at all."""
    row = session.scalars(
        select(WorkingHours).where(WorkingHours.date == day.isoformat())
    ).one_or_none()
    if row is None:
        row = session.scalars(
            select(WorkingHours).where(WorkingHours.weekday == day.weekday())
        ).one_or_none()
    if row is None:
        return None
    if row.is_closed:
        # The times of a closed day are never read, and parsing them first
        # turns a blank or NULL into an AttributeError on a page render.
        return DayHours(open_min=0, close_min=0, is_closed=True)
    return DayHours(open_min=_to_minutes(row.start),
                    close_min=_to_minutes(row.end),
                    is_closed=False)


def _wall_minutes(moment: datetime) -> int:
    """Minutes past local midnight. The grid is a wall clock, so this is the
    right measure here and elapsed time is not: on the autumn Sunday an hour
    of real time occupies no rows at all."""
    return moment.hour * 60 + moment.minute


def _wall_span(visit: Visit) -> tuple[int, int]:
    """The Visit's start and end as minutes past its own local midnight.

    A Visit running past midnight is cut at it: the day column below has no
    room for a block that starts before its first row, and phase 1 books
    inside working hours anyway.
    """
    start = timeutil.from_utc_iso(visit.starts_at)
    end = timeutil.from_utc_iso(visit.ends_at)
    first = _wall_minutes(start)
    last = _wall_minutes(end) if end.date() == start.date() else DAY_END_MIN
    return first, max(last, first + SLOT_MIN)


def week_grid(session: Session, monday: date) -> WeekGrid:
    days_dates = [monday + timedelta(days=i) for i in range(7)]
    hours = {d: hours_for(session, d) for d in days_dates}

    open_days = [h for h in hours.values() if h and not h.is_closed]
    start_min = min((h.open_min for h in open_days), default=FALLBACK_OPEN_MIN)
    end_min = max((h.close_min for h in open_days), default=FALLBACK_CLOSE_MIN)

    window_start = datetime.combine(monday, datetime.min.time(),
                                    tzinfo=timeutil.LOCAL)
    window_end = window_start + timedelta(days=7)
    stmt = (select(Visit)
            .where(Visit.deleted_at.is_(None),
                   Visit.status.in_(DRAWN_STATUSES),
                   Visit.starts_at >= timeutil.to_utc_iso(window_start),
                   Visit.starts_at < timeutil.to_utc_iso(window_end))
            .order_by(Visit.starts_at))
    visits = list(session.scalars(stmt))

    # The grid covers the working hours and every Visit that exists. Clamping a
    # 18:00 Visit onto the last row of a day that closes at 17:00 would draw it
    # at a time it does not happen, next to or on top of a real 16:45 one, and
    # the block below 45 minutes shows no time of its own to contradict it.
    for visit in visits:
        first, last = _wall_span(visit)
        start_min = min(start_min, first)
        end_min = max(end_min, last)
    start_min = start_min // SLOT_MIN * SLOT_MIN
    end_min = -(-end_min // SLOT_MIN) * SLOT_MIN
    rows = max(1, -(-(end_min - start_min) // SLOT_MIN))

    by_day: dict[date, list[VisitBlock]] = {d: [] for d in days_dates}
    for visit in visits:
        first, last = _wall_span(visit)
        row_start = (first - start_min) // SLOT_MIN + 1
        row_end = -(-(last - start_min) // SLOT_MIN)
        names = [i.treatment.name for i in visit.items
                 if i.kind == "treatment" and i.treatment is not None]
        by_day[timeutil.from_utc_iso(visit.starts_at).date()].append(VisitBlock(
            visit_id=visit.id,
            client_name=visit.client.name,
            # the wording never leaves the service for a grid, only the dot
            has_alert=bool(visit.client.alert and visit.client.alert.strip()),
            label=", ".join(names),
            status=visit.status,
            starts_at=visit.starts_at,
            ends_at=visit.ends_at,
            row_start=row_start,
            row_span=max(1, row_end - row_start + 1),
        ))

    columns = []
    for d in days_dates:
        h = hours[d]
        columns.append(DayColumn(
            date=d,
            is_closed=h is None or h.is_closed,
            open_min=h.open_min if h and not h.is_closed else start_min,
            close_min=h.close_min if h and not h.is_closed else end_min,
            blocks=by_day[d],
        ))
    return WeekGrid(monday=monday, start_min=start_min, end_min=end_min,
                    rows=rows, days=columns)
