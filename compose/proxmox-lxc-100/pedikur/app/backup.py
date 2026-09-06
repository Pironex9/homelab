"""SQLite online backup. Never copy a live WAL database with cp."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

KEEP_DAILY = 7


def snapshot(db_path: Path, dest_dir: Path, tag: str = "daily") -> Path | None:
    """Copy the database consistently while it is in use. Returns the path,
    or None when there is no database to copy yet."""
    if not db_path.exists():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / f"{tag}-{stamp}.sqlite"
    source = sqlite3.connect(db_path)
    target = sqlite3.connect(dest)
    try:
        with target:
            source.backup(target)
    finally:
        target.close()
        source.close()
    return dest


def prune(dest_dir: Path, tag: str = "daily", keep: int = KEEP_DAILY) -> None:
    files = sorted(dest_dir.glob(f"{tag}-*.sqlite"), reverse=True)
    for stale in files[keep:]:
        stale.unlink()


async def nightly_task(db_path: Path, dest_dir: Path) -> None:
    """Snapshot once a day. Runs for the life of the process."""
    while True:
        await asyncio.sleep(24 * 60 * 60)
        try:
            snapshot(db_path, dest_dir, tag="daily")
            prune(dest_dir, tag="daily")
        except Exception:  # a failed backup must not kill the app
            pass
