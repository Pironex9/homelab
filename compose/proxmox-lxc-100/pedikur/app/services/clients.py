"""Client queries.

Search returns a projection, not the model: the alert TEXT must never travel
to a list screen, only the fact that one exists. The Today and Clients screens
show a red dot; the wording lives inside the card.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import fold
from app.models import Client, Visit


@dataclass(frozen=True)
class ClientRow:
    id: int
    name: str
    phone: str | None
    has_alert: bool
    archived: bool


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _like_needle(query: str) -> str:
    """% and _ are LIKE wildcards. A search for "%" must find the clients whose
    name contains a percent sign, which is none of them, not all of them."""
    escaped = (fold(query).replace("\\", "\\\\")
               .replace("%", "\\%").replace("_", "\\_"))
    return f"%{escaped}%"


def search(session: Session, query: str, limit: int = 20,
           include_archived: bool = False) -> list[ClientRow]:
    """Archived clients are out unless asked for. Erased ones are out always:
    Erase is the GDPR action, and there is no screen that un-erases."""
    stmt = select(Client).where(Client.erased_at.is_(None))
    if not include_archived:
        stmt = stmt.where(Client.archived_at.is_(None))
    if query.strip():
        stmt = stmt.where(
            func.fold(Client.name).like(_like_needle(query.strip()), escape="\\"))
    stmt = stmt.order_by(func.fold(Client.name)).limit(limit)
    return [
        ClientRow(id=c.id, name=c.name, phone=c.phone,
                  has_alert=bool(c.alert and c.alert.strip()),
                  archived=c.archived_at is not None)
        for c in session.scalars(stmt)
    ]


def get(session: Session, client_id: int) -> Client | None:
    return session.get(Client, client_id)


def create(session: Session, name: str, phone: str | None,
           created_by: str, **optional) -> Client:
    name = name.strip()
    if not name:
        raise ValueError("a client needs a name")
    client = Client(name=name, phone=phone, created_by=created_by,
                    created_at=_now(), **optional)
    session.add(client)
    session.flush()
    return client


# setattr on a declarative instance succeeds for any name: an unmapped one
# becomes a plain Python attribute, flush reports success, and nothing is
# written. A typo in an Erase would be a GDPR request silently not honoured.
_FIELDS = frozenset(Client.__mapper__.columns.keys())


def update(session: Session, client_id: int, **fields) -> Client:
    unknown = set(fields) - _FIELDS
    if unknown:
        raise ValueError(f"not columns of client: {sorted(unknown)}")
    client = session.get(Client, client_id)
    if client is None:
        raise LookupError(f"no client {client_id}")
    if "name" in fields and not (fields["name"] or "").strip():
        raise ValueError("a client needs a name")
    for key, value in fields.items():
        setattr(client, key, value.strip() if isinstance(value, str) else value)
    session.flush()
    return client


def archive(session: Session, client_id: int) -> None:
    """Removed from the working lists, every record kept. Reversible.
    This is not Erase: Erase empties the identifying and health fields and is
    admin only, and arrives with the GDPR work in a later phase."""
    update(session, client_id, archived_at=_now())


def unarchive(session: Session, client_id: int) -> None:
    update(session, client_id, archived_at=None)


def history(session: Session, client_id: int) -> list[Visit]:
    stmt = (select(Visit)
            .where(Visit.client_id == client_id,
                   Visit.status == "done",
                   Visit.deleted_at.is_(None))
            .order_by(Visit.starts_at.desc()))
    return list(session.scalars(stmt))
