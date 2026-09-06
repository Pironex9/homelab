"""Engine and session handling. One writer, so the pragmas do the work."""
from __future__ import annotations

import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def fold(text: str | None) -> str | None:
    """Lower case and strip accents, for search.

    SQLite folds ASCII only: LIKE '%kovacs%' does not match "Kovacs" spelled
    with its accents, and LIKE '%KOVACS%' with accents does not match the same
    name in lower case. On a phone keyboard the accents are the slow keys, so
    the search she actually types would return nothing.
    """
    if text is None:
        return None
    return "".join(ch for ch in unicodedata.normalize("NFKD", text.casefold())
                   if not unicodedata.combining(ch))


def make_engine(db_path: Path):
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"timeout": 5.0},  # busy_timeout, also set as a pragma below
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA busy_timeout = 5000")
        cur.execute("PRAGMA synchronous = NORMAL")
        cur.close()
        # deterministic, so the query planner may use it in an index later
        dbapi_connection.create_function("fold", 1, fold, deterministic=True)

    return engine


class Database:
    def __init__(self, db_path: Path) -> None:
        self.engine = make_engine(db_path)
        self._factory = sessionmaker(bind=self.engine, future=True,
                                     expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
