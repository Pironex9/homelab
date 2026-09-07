"""JSON surface for scripting and, from phase 4, an MCP server.

Reachable only from the internal network: the reverse proxy denies /api/* on
the public route, and the MCP host talks to 192.168.0.110 directly. The token
is the second layer, because our own rule says we do not trust a proxy config
to be right - including our own deny rule.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from decimal import Decimal

from fastapi import (APIRouter, Depends, Header, HTTPException, Query,
                     Request, status)
from sqlalchemy import select

from app.models import Visit
from app.services import clients, timeutil, treatments, visits

# SQLite's INTEGER tops out at 2**63; anything larger is an OverflowError at
# bind time, wrapped by SQLAlchemy into something neither handler catches.
MAX_ID = 2 ** 63 - 1
MAX_VISITS = 2000


def _authorise(request: Request,
               authorization: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.api_token
    scheme, _, presented = (authorization or "").partition(" ")
    # the scheme is case-insensitive per RFC 7235
    if scheme.lower() != "bearer" or not presented:
        raise _unauthorised()
    try:
        ok = secrets.compare_digest(presented, expected)
    except TypeError:
        # compare_digest refuses a non-ASCII str, and Starlette decodes headers
        # as latin-1, so raw bytes on the wire reach it. A crafted header is
        # not a server fault.
        ok = False
    if not ok:
        raise _unauthorised()


def _unauthorised() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                         headers={"WWW-Authenticate": "Bearer"})


# As a router dependency, not a first statement: FastAPI validates path, query
# and body before it calls a handler, so an in-handler check answered 422 to a
# caller with no token at all, naming the parameters it was missing.
router = APIRouter(prefix="/api", dependencies=[Depends(_authorise)])


def _row_id(value) -> int:
    """A row id that SQLite can actually bind. int() alone accepts an
    arbitrary precision JSON integer, which raises OverflowError at bind time,
    wrapped into something neither handler catches."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"not a row id: {value!r}")
    if not 1 <= value <= MAX_ID:
        raise ValueError(f"row id out of range: {value}")
    return value


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _local(text: str, field: str) -> datetime:
    """A local ISO datetime from the payload. as_local, not replace(tzinfo=),
    so an offset already present is honoured and a wall clock time the spring
    forward skipped is refused rather than silently moved an hour."""
    try:
        return timeutil.as_local(datetime.fromisoformat(text))
    except (TypeError, ValueError) as exc:
        raise _bad_request(f"{field}: {exc}") from None


@router.get("/clients")
def api_clients(request: Request, q: str = ""):
    with request.app.state.db.session() as s:
        # the search projection, so the alert wording never leaves the service
        return [{"id": c.id, "name": c.name, "phone": c.phone,
                 "has_alert": c.has_alert}
                for c in clients.search(s, q, limit=1000)]


@router.get("/treatments")
def api_treatments(request: Request):
    with request.app.state.db.session() as s:
        return [{"id": t.id, "name": t.name, "duration_min": t.duration_min,
                 "price_cents": t.price_cents, "active": bool(t.active)}
                for t in treatments.list_all(s)]


@router.get("/visits")
def api_visits(request: Request,
               date_from: str = Query(alias="from"),
               date_to: str = Query(alias="to")):
    """from and to are local dates, YYYY-MM-DD, inclusive of from and
    exclusive of to."""
    start = _local(f"{date_from}T00:00", "from")
    end = _local(f"{date_to}T00:00", "to")
    with request.app.state.db.session() as s:
        rows = s.scalars(
            select(Visit).where(
                Visit.deleted_at.is_(None),
                Visit.starts_at >= timeutil.to_utc_iso(start),
                Visit.starts_at < timeutil.to_utc_iso(end)
            ).order_by(Visit.starts_at).limit(MAX_VISITS))
        # an erased client's name must not come back out through their history
        rows = [v for v in rows if not v.client.erased_at]
        return [{
            "id": v.id,
            "client": v.client.name,
            "starts_at": v.starts_at,
            "ends_at": v.ends_at,
            "status": v.status,
            # qty is REAL, so the product is a float and money would leave
            # the app as 2500.0. Half up, like parse_price: round() is banker's
            # rounding, so two visits of identical value could differ by a cent.
            "total_cents": _total_cents(v),
            "treatments": [i.treatment.name for i in v.items
                           if i.kind == "treatment" and i.treatment],
        } for v in rows]


def _total_cents(visit: Visit) -> int:
    total = Decimal(0)
    for item in visit.items:
        total += Decimal(item.unit_price_cents) * Decimal(str(item.qty))
    return int(total.to_integral_value(rounding="ROUND_HALF_UP"))


async def _json_body(request: Request) -> dict:
    """Read the body here rather than declaring it as Body(...).

    FastAPI parses a declared body while it solves the handler's parameters,
    which happens after the router dependency but produces its own 422 before
    the handler runs, so a caller with no token learned that its JSON was
    malformed. Reading it here keeps every unauthenticated answer a 401.
    """
    try:
        payload = await request.json()
    except Exception:
        raise _bad_request("body has to be a JSON object") from None
    if not isinstance(payload, dict):
        raise _bad_request("body has to be a JSON object")
    return payload


@router.post("/clients", status_code=201)
async def api_create_client(request: Request):
    payload = await _json_body(request)
    name = payload.get("name")
    phone = payload.get("phone")
    if not isinstance(name, str):
        raise _bad_request("name is required")
    if phone is not None and not isinstance(phone, str):
        # a dict or a list reaches the bind parameter and raises out of
        # sqlite3 as something neither handler catches
        raise _bad_request("phone has to be a string")
    try:
        with request.app.state.db.session() as s:
            client = clients.create(s, name, phone, created_by="api")
            return {"id": client.id}
    except ValueError as exc:
        raise _bad_request(str(exc)) from None


@router.post("/visits", status_code=201)
async def api_create_visit(request: Request):
    payload = await _json_body(request)
    try:
        client_id = _row_id(payload["client_id"])
        raw_ids = payload["treatment_ids"]
        if not isinstance(raw_ids, list):
            # a bare "12" would iterate into [1, 2]: two bookings from a typo
            raise TypeError("treatment_ids has to be a list")
        treatment_ids = [_row_id(i) for i in raw_ids]
        starts_text = str(payload["starts_at"])
    except (KeyError, TypeError, ValueError):
        raise _bad_request(
            "client_id, starts_at and treatment_ids are required") from None
    starts = _local(starts_text, "starts_at")
    try:
        with request.app.state.db.session() as s:
            visit = visits.book(s, client_id, starts, treatment_ids,
                                created_by="api")
            return {"id": visit.id}
    except visits.SlotTaken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="slot taken") from None
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from None
    except ValueError as exc:
        raise _bad_request(str(exc)) from None
