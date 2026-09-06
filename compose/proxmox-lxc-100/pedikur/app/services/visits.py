"""Booking and the Visit lifecycle.

A Visit is one client session, booked ahead or walked in. Booking and
treatment record are the same row at different points in its life, which is
why there is no separate visit table: two rows a day apart would contribute a
zero-day gap to the Visit Interval median and, after a few of those, mark
everyone permanently overdue.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Client, Treatment, Visit, VisitItem
from app.services import timeutil

ACTIVE_STATUSES = ("planned", "done")
STATUSES = ("planned", "done", "cancelled", "no_show")


class SlotTaken(Exception):
    """Another Visit already occupies the requested window."""


def overlapping(session: Session, start_utc: str, end_utc: str,
                exclude_id: int | None = None) -> list[Visit]:
    """Half open intervals: 10:00-10:45 and 10:45-11:15 do not overlap, or
    every back to back booking would be refused."""
    stmt = (select(Visit)
            .where(Visit.status.in_(ACTIVE_STATUSES),
                   Visit.deleted_at.is_(None),
                   Visit.starts_at < end_utc,
                   Visit.ends_at > start_utc))
    if exclude_id is not None:
        stmt = stmt.where(Visit.id != exclude_id)
    return list(session.scalars(stmt))


def _treatments(session: Session, treatment_ids: list[int]) -> list[Treatment]:
    found = {t.id: t for t in session.scalars(
        select(Treatment).where(Treatment.id.in_(treatment_ids)))}
    missing = [i for i in treatment_ids if i not in found]
    if missing:
        raise LookupError(f"unknown treatment ids: {missing}")
    return [found[i] for i in treatment_ids]


def book(session: Session, client_id: int, starts_at_local: datetime,
         treatment_ids: list[int], created_by: str,
         ends_at_local: datetime | None = None) -> Visit:
    """Create a planned Visit.

    ends_at defaults to the summed duration of the treatments and may be
    widened by hand. The overlap check runs inside this transaction: checking
    first and inserting after is a race even with two users and two tabs.
    """
    if not treatment_ids:
        raise ValueError("a Visit needs at least one Treatment")
    # Checked here rather than left to the foreign key: an IntegrityError at
    # commit escapes the router as a 500, a LookupError becomes a message.
    if session.get(Client, client_id) is None:
        raise LookupError(f"no client {client_id}")
    chosen = _treatments(session, treatment_ids)
    total_min = sum(t.duration_min for t in chosen)
    computed_end = starts_at_local + timedelta(minutes=total_min)
    end_local = max(ends_at_local, computed_end) if ends_at_local else computed_end

    start_utc = timeutil.to_utc_iso(starts_at_local)
    end_utc = timeutil.to_utc_iso(end_local)
    if overlapping(session, start_utc, end_utc):
        raise SlotTaken(f"{start_utc} .. {end_utc}")

    visit = Visit(client_id=client_id, starts_at=start_utc, ends_at=end_utc,
                  status="planned", created_by=created_by,
                  created_at=timeutil.to_utc_iso(timeutil.local_now()))
    for treatment in chosen:
        visit.items.append(VisitItem(kind="treatment",
                                     treatment_id=treatment.id, qty=1,
                                     unit_price_cents=treatment.price_cents))
    session.add(visit)
    session.flush()
    return visit


def add_treatment(session: Session, visit_id: int, treatment_id: int) -> Visit:
    """Add a Treatment to an existing Visit.

    ends_at only ever grows: if she widened the window by hand, adding a
    treatment must not shrink it back behind her.
    """
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    treatment = session.get(Treatment, treatment_id)
    if treatment is None:
        raise LookupError(f"no treatment {treatment_id}")

    # Appended to the relationship, not inserted by visit_id. Visit.items is
    # lazy="selectin", so session.get above already loaded it; a row inserted
    # behind its back leaves the collection stale and the sum below would drop
    # exactly the treatment we are adding.
    visit.items.append(VisitItem(kind="treatment", treatment_id=treatment.id,
                                 qty=1,
                                 unit_price_cents=treatment.price_cents))
    session.flush()

    total_min = sum(i.treatment.duration_min for i in visit.items
                    if i.kind == "treatment" and i.treatment is not None)
    needed_end = timeutil.from_utc_iso(visit.starts_at) + timedelta(minutes=total_min)
    if needed_end > timeutil.from_utc_iso(visit.ends_at):
        visit.ends_at = timeutil.to_utc_iso(needed_end)
    session.flush()
    return visit


def reschedule(session: Session, visit_id: int, starts_at_local: datetime,
               ends_at_local: datetime) -> Visit:
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    if ends_at_local <= starts_at_local:
        raise ValueError("a Visit has to end after it starts")
    start_utc = timeutil.to_utc_iso(starts_at_local)
    end_utc = timeutil.to_utc_iso(ends_at_local)
    if overlapping(session, start_utc, end_utc, exclude_id=visit_id):
        raise SlotTaken(f"{start_utc} .. {end_utc}")
    visit.starts_at, visit.ends_at = start_utc, end_utc
    session.flush()
    return visit


def set_status(session: Session, visit_id: int, status: str) -> Visit:
    if status not in STATUSES:
        raise ValueError(f"bad status: {status}")
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    visit.status = status
    session.flush()
    return visit


def unclosed(session: Session) -> list[Visit]:
    """Visits whose window has passed but were never closed.

    They are never closed automatically. Auto-closing would invent revenue
    from a client who may not have come; auto-marking no_show would invent the
    opposite. It also matters beyond the money: the Visit Interval counts only
    done Visits, so an unclosed one makes a client look as if they never came
    and puts them on the Recall List weeks early.
    """
    now_utc = timeutil.to_utc_iso(timeutil.local_now())
    stmt = (select(Visit)
            .where(Visit.status == "planned",
                   Visit.deleted_at.is_(None),
                   Visit.ends_at < now_utc)
            .order_by(Visit.starts_at))
    return list(session.scalars(stmt))
