import sqlite3
import pytest
from app import backup


def test_snapshot_copies_a_live_database(db_path, tmp_path):
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE t (x)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()

    dest = backup.snapshot(db_path, tmp_path / "b", tag="daily")
    assert dest is not None and dest.stat().st_size > 0

    copy = sqlite3.connect(dest)
    assert copy.execute("SELECT x FROM t").fetchone()[0] == 1
    copy.close()
    con.close()


def test_snapshot_of_a_missing_database_is_a_no_op(db_path, tmp_path):
    assert backup.snapshot(db_path, tmp_path / "b") is None


def test_a_failed_snapshot_leaves_no_file_behind(db_path, tmp_path):
    """A zero byte leftover would sort newest and be the one a restore grabs."""
    db_path.write_text("this is not a database")
    dest_dir = tmp_path / "b"
    with pytest.raises(sqlite3.DatabaseError):
        backup.snapshot(db_path, dest_dir, tag="daily")
    assert list(dest_dir.glob("*.sqlite")) == []


def test_prune_keeps_the_newest(tmp_path):
    for n in range(10):
        (tmp_path / f"daily-2026090{n}T000000Z.sqlite").write_text("x")
    backup.prune(tmp_path, tag="daily", keep=7)
    left = sorted(p.name for p in tmp_path.glob("daily-*.sqlite"))
    assert len(left) == 7
    assert left[0] == "daily-20260903T000000Z.sqlite"
