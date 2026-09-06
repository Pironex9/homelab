"""Numbered SQL migrations, applied at startup inside a transaction.

No Alembic: what it would add is downgrade scripts we would never run, and on
SQLite its autogenerate needs render_as_batch=True or it emits statements
SQLite cannot execute. create_all is not an option either - it creates missing
tables and never adds a column to an existing one.

SQLite DDL is transactional, so a migration that fails half way leaves no
half-built schema.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app import backup

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _applied(con: sqlite3.Connection) -> set[str]:
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "  filename TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    return {row[0] for row in con.execute("SELECT filename FROM schema_version")}


def run(db_path: Path, backup_dir: Path,
        migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every migration newer than the recorded version.

    Returns the filenames applied, oldest first. Empty when up to date.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in migrations_dir.glob("*.sql"))

    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        done = _applied(con)
        pending = [p for p in files if p.name not in done]
        if not pending:
            return []
    finally:
        con.close()

    # Snapshot before touching the schema. Cheap, and it turns a bad migration
    # into seconds of loss rather than falling back to last midnight.
    # Skipped on a fresh database: sqlite3.connect above already created the
    # file, so it exists but holds nothing worth keeping.
    if done:
        backup.snapshot(db_path, backup_dir, tag="pre-migration")

    applied: list[str] = []
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        for path in pending:
            with con:  # one transaction per migration
                con.executescript(path.read_text())
                con.execute(
                    "INSERT INTO schema_version (filename) VALUES (?)",
                    (path.name,),
                )
            applied.append(path.name)
    finally:
        con.close()
    return applied
