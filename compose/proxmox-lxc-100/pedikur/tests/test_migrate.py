import sqlite3
import pytest
from app import migrate


def test_migrate_creates_schema_and_is_idempotent(db_path, tmp_path):
    first = migrate.run(db_path, backup_dir=tmp_path / "backup")
    # equality, not membership: order is the whole point of numbered files
    assert first == ["001_schema.sql", "002_seed.sql"]

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
    snaps = list(backup_dir.glob("pre-migration-*.sqlite"))
    assert len(snaps) == 1

    # the snapshot has to be a real database, not just a file that exists
    con = sqlite3.connect(snaps[0])
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert con.execute(
        "SELECT COUNT(*) FROM working_hours").fetchone()[0] == 5
    con.close()


def test_a_failing_migration_leaves_the_database_untouched(db_path, tmp_path):
    """The claim the whole module rests on: executescript() commits on its own
    unless the script carries its own BEGIN and COMMIT."""
    backup_dir = tmp_path / "backup"
    migrate.run(db_path, backup_dir=backup_dir)

    pending = db_path.parent
    (pending / "003_broken.sql").write_text(
        "CREATE TABLE half_built (x);\n"
        "ALTER TABLE client ADD COLUMN nickname TEXT;\n"
        "CREATE TABLE THIS IS NOT SQL;\n"
    )
    with pytest.raises(sqlite3.OperationalError):
        migrate.run(db_path, backup_dir=backup_dir, migrations_dir=pending)

    con = sqlite3.connect(db_path)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "half_built" not in tables
    columns = {r[1] for r in con.execute("PRAGMA table_info(client)")}
    assert "nickname" not in columns
    assert {r[0] for r in con.execute("SELECT filename FROM schema_version")} == {
        "001_schema.sql", "002_seed.sql"}
    con.close()

    # and the fixed migration then applies cleanly, without manual surgery
    (pending / "003_broken.sql").write_text(
        "ALTER TABLE client ADD COLUMN nickname TEXT;\n")
    assert migrate.run(db_path, backup_dir=backup_dir,
                       migrations_dir=pending) == ["003_broken.sql"]
