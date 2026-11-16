"""SQLite online backup. Never copy a live WAL database with cp."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

KEEP_DAILY = 7
INTERVAL_SECONDS = 24 * 60 * 60


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
    except Exception:
        # sqlite3.connect(dest) already created the file. Leaving it behind
        # would put a zero byte file at the top of the sorted list, which is
        # exactly the one a restore reaches for and the one prune keeps.
        target.close()
        dest.unlink(missing_ok=True)
        raise
    finally:
        target.close()
        source.close()
    return dest


def prune(dest_dir: Path, tag: str = "daily", keep: int = KEEP_DAILY) -> None:
    files = sorted(dest_dir.glob(f"{tag}-*.sqlite"), reverse=True)
    for stale in files[keep:]:
        stale.unlink()


async def nightly_task(db_path: Path, dest_dir: Path) -> None:
    """Snapshot once a day, starting at boot. Runs for the life of the process.

    The first copy is taken immediately rather than 24 hours in: a container
    that gets redeployed most days would otherwise never produce one.
    The clock is the process start time, not a wall clock hour.
    """
    while True:
        try:
            snapshot(db_path, dest_dir, tag="daily")
            prune(dest_dir, tag="daily")
        except Exception:  # a failed backup must not kill the app
            log.exception("daily backup failed")
        await asyncio.sleep(INTERVAL_SECONDS)
