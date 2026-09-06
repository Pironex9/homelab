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
        # pysqlite opens a transaction lazily, and only just before a write.
        # That makes every check-then-write a race: two bookings both read the
        # slot as free, then both insert, and the day is double booked.
        # Measured: two threads, two visits in the same window, both committed.
        # Handing transaction control to SQLAlchemy lets us BEGIN IMMEDIATE.
        dbapi_connection.isolation_level = None
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA busy_timeout = 5000")
        cur.execute("PRAGMA synchronous = NORMAL")
        cur.close()
        # Deterministic so SQLite may cache it within a statement. Never build
        # an index on fold(name): SQLite accepts it, and the database then
        # cannot be written or even integrity-checked by any connection that
        # has not registered the function, which is every sqlite3 CLI and the
        # weekly restore verification in scripts/restore-test.sh.
        dbapi_connection.create_function("fold", 1, fold, deterministic=True)

    @event.listens_for(engine, "begin")
    def _begin_immediate(connection):
        # Every transaction takes the write lock up front, reads included.
        # ponytail: blunt, and right for one practitioner on one device. If
        # read traffic ever matters, make this per-service and give the
        # booking path its own immediate session instead.
        connection.exec_driver_sql("BEGIN IMMEDIATE")

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
