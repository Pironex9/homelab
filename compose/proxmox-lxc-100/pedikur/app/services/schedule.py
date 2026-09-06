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
    return DayHours(open_min=_to_minutes(row.start),
                    close_min=_to_minutes(row.end),
                    is_closed=bool(row.is_closed))


def _wall_minutes(moment: datetime) -> int:
    """Minutes past local midnight. The grid is a wall clock, so this is the
    right measure here and elapsed time is not: on the autumn Sunday an hour
    of real time occupies no rows at all."""
    return moment.hour * 60 + moment.minute


def week_grid(session: Session, monday: date) -> WeekGrid:
    days_dates = [monday + timedelta(days=i) for i in range(7)]
    hours = {d: hours_for(session, d) for d in days_dates}

    open_days = [h for h in hours.values() if h and not h.is_closed]
    start_min = min((h.open_min for h in open_days), default=FALLBACK_OPEN_MIN)
    end_min = max((h.close_min for h in open_days), default=FALLBACK_CLOSE_MIN)
    rows = max(1, (end_min - start_min) // SLOT_MIN)

    window_start = datetime.combine(monday, datetime.min.time(),
                                    tzinfo=timeutil.LOCAL)
    window_end = window_start + timedelta(days=7)
    stmt = (select(Visit)
            .where(Visit.deleted_at.is_(None),
                   Visit.status.in_(("planned", "done")),
                   Visit.starts_at >= timeutil.to_utc_iso(window_start),
                   Visit.starts_at < timeutil.to_utc_iso(window_end))
            .order_by(Visit.starts_at))

    by_day: dict[date, list[VisitBlock]] = {d: [] for d in days_dates}
    for visit in session.scalars(stmt):
        local_start = timeutil.from_utc_iso(visit.starts_at)
        local_end = timeutil.from_utc_iso(visit.ends_at)
        day = local_start.date()
        if day not in by_day:
            continue
        # Both ends are placed on the same wall clock, so the span comes out of
        # the row numbers rather than a subtraction that would be wall clock in
        # one place and elapsed time in another.
        first_row = (_wall_minutes(local_start) - start_min) // SLOT_MIN + 1
        last_row = -(-(_wall_minutes(local_end) - start_min) // SLOT_MIN)
        # Clamped: a span that runs past the last row makes CSS grid invent
        # rows, and that column then renders taller than every other one.
        row_start = min(max(1, first_row), rows)
        row_end = min(max(row_start, last_row), rows)
        names = [i.treatment.name for i in visit.items
                 if i.kind == "treatment" and i.treatment is not None]
        by_day[day].append(VisitBlock(
            visit_id=visit.id,
            client_name=visit.client.name,
            # the wording never leaves the service for a grid, only the dot
            has_alert=bool(visit.client.alert and visit.client.alert.strip()),
            label=", ".join(names),
            status=visit.status,
            starts_at=visit.starts_at,
            ends_at=visit.ends_at,
            row_start=row_start,
            row_span=row_end - row_start + 1,
        ))

    columns = []
    for d in days_dates:
        h = hours[d]
        columns.append(DayColumn(
            date=d,
            is_closed=h is None or h.is_closed,
            open_min=h.open_min if h else start_min,
            close_min=h.close_min if h else end_min,
            blocks=by_day[d],
        ))
    return WeekGrid(monday=monday, start_min=start_min, end_min=end_min,
                    rows=rows, days=columns)
