"""Engine and session handling. One writer, so the pragmas do the work."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


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
