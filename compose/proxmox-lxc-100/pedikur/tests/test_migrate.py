import sqlite3
from app import migrate


def test_migrate_creates_schema_and_is_idempotent(db_path, tmp_path):
    first = migrate.run(db_path, backup_dir=tmp_path / "backup")
    assert "001_schema.sql" in first
    assert "002_seed.sql" in first

    con = sqlite3.connect(db_path)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"user", "client", "treatment", "visit", "visit_item",
            "working_hours", "setting"} <= tables
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    # seeded defaults
    hours = con.execute(
        "SELECT COUNT(*) FROM working_hours WHERE weekday IS NOT NULL").fetchone()[0]
    assert hours == 5
    buffer_min = con.execute(
        "SELECT value FROM setting WHERE key='buffer_min'").fetchone()[0]
    assert buffer_min == "15"
    con.close()

    second = migrate.run(db_path, backup_dir=tmp_path / "backup")
    assert second == []


def test_migrate_snapshots_before_applying(db_path, tmp_path):
    backup_dir = tmp_path / "backup"
    migrate.run(db_path, backup_dir=backup_dir)
    # first run has nothing to snapshot: the file does not exist yet
    assert not list(backup_dir.glob("*.sqlite"))

    (db_path.parent / "003_noop.sql").write_text("SELECT 1;")
    migrate.run(db_path, backup_dir=backup_dir,
                migrations_dir=db_path.parent)
    assert len(list(backup_dir.glob("pre-migration-*.sqlite"))) == 1
