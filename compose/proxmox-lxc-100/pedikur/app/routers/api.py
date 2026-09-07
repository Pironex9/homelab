"""JSON surface for scripting and, from phase 4, an MCP server.

Reachable only from the internal network: the reverse proxy denies /api/* on
the public route, and the MCP host talks to 192.168.0.110 directly. The token
is the second layer, because our own rule says we do not trust a proxy config
to be right - including our own deny rule.
"""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import (APIRouter, Body, Header, HTTPException, Query, Request,
                     status)
from sqlalchemy import select

from app.models import Visit
from app.services import clients, timeutil, treatments, visits

router = APIRouter(prefix="/api")


def _authorise(request: Request, authorization: str | None) -> None:
    expected = request.app.state.settings.api_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    presented = authorization.removeprefix("Bearer ")
    try:
        ok = secrets.compare_digest(presented, expected)
    except TypeError:
        # compare_digest refuses non-ASCII str, and a crafted header is not a
        # server fault
        ok = False
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


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
def api_clients(request: Request, q: str = "",
                authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    with request.app.state.db.session() as s:
        # the search projection, so the alert wording never leaves the service
        return [{"id": c.id, "name": c.name, "phone": c.phone,
                 "has_alert": c.has_alert}
                for c in clients.search(s, q, limit=1000)]


@router.get("/treatments")
def api_treatments(request: Request,
                   authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    with request.app.state.db.session() as s:
        return [{"id": t.id, "name": t.name, "duration_min": t.duration_min,
                 "price_cents": t.price_cents, "active": bool(t.active)}
                for t in treatments.list_all(s)]


@router.get("/visits")
def api_visits(request: Request,
               date_from: str = Query(alias="from"),
               date_to: str = Query(alias="to"),
               authorization: str | None = Header(default=None)):
    """from and to are local dates, YYYY-MM-DD, inclusive of from and
    exclusive of to."""
    _authorise(request, authorization)
    start = _local(f"{date_from}T00:00", "from")
    end = _local(f"{date_to}T00:00", "to")
    with request.app.state.db.session() as s:
        rows = s.scalars(
            select(Visit).where(
                Visit.deleted_at.is_(None),
                Visit.starts_at >= timeutil.to_utc_iso(start),
                Visit.starts_at < timeutil.to_utc_iso(end)
            ).order_by(Visit.starts_at))
        return [{
            "id": v.id,
            "client": v.client.name,
            "starts_at": v.starts_at,
            "ends_at": v.ends_at,
            "status": v.status,
            # rounded: qty is REAL, so the product is a float and money would
            # leave the app as 2500.0
            "total_cents": round(sum(i.unit_price_cents * i.qty
                                     for i in v.items)),
            "treatments": [i.treatment.name for i in v.items
                           if i.kind == "treatment" and i.treatment],
        } for v in rows]


@router.post("/clients", status_code=201)
def api_create_client(request: Request, payload: dict = Body(...),
                      authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    name = payload.get("name")
    if not isinstance(name, str):
        raise _bad_request("name is required")
    try:
        with request.app.state.db.session() as s:
            client = clients.create(s, name, payload.get("phone"),
                                    created_by="api")
            return {"id": client.id}
    except ValueError as exc:
        raise _bad_request(str(exc)) from None


@router.post("/visits", status_code=201)
def api_create_visit(request: Request, payload: dict = Body(...),
                     authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    try:
        client_id = int(payload["client_id"])
        treatment_ids = [int(i) for i in payload["treatment_ids"]]
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
