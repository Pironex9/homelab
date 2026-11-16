import sqlite3

import pytest
from app import migrate


@pytest.fixture
def con(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    c = sqlite3.connect(db_path)
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("INSERT INTO user (id, name, username, role, password_hash) "
              "VALUES (1, 'A', 'a', 'adult', 'x')")
    yield c
    c.close()


def _entry(con, amount=100, recurring_id=None, month=None):
    con.execute(
        "INSERT INTO entry (wallet_id, kind, status, date, amount_minor, "
        "currency, eur_minor, fx_rate, payment, source, created_by, created_at, "
        "recurring_id, recurring_month) "
        "VALUES (1, 'expense', 'confirmed', '2026-11-01', ?, 'EUR', ?, '1', "
        "'cash', 'manual', 1, '2026-11-01T00:00:00Z', ?, ?)",
        (amount, amount, recurring_id, month))


def test_seed_has_one_household_wallet(con):
    rows = con.execute(
        "SELECT name FROM wallet WHERE owner_user_id IS NULL").fetchall()
    assert rows == [("Közös",)]
    assert con.execute("SELECT COUNT(*) FROM wallet").fetchone()[0] == 1


def test_amount_must_be_positive(con):
    with pytest.raises(sqlite3.IntegrityError):
        _entry(con, amount=0)


def test_recurring_month_unique(con):
    con.execute("INSERT INTO category (id, name, kind) VALUES (900, 'T', 'expense')")
    con.execute("INSERT INTO recurring (id, name, kind, category_id, amount_minor, "
                "currency, day_of_month) VALUES (1, 'R', 'expense', 900, 100, 'EUR', 1)")
    _entry(con, recurring_id=1, month="2026-11")
    with pytest.raises(sqlite3.IntegrityError):
        _entry(con, recurring_id=1, month="2026-11")


def test_zsebpenz_category_exists(con):
    assert con.execute(
        "SELECT kind FROM category WHERE name = 'Zsebpénz'").fetchone() == ("expense",)


def test_seed_category_order(con):
    names = [r[0] for r in con.execute(
        "SELECT name FROM category WHERE kind='expense' ORDER BY sort, id")]
    assert names[:3] == ["Élelmiszer", "Háztartás", "Higiénia"]
    assert names[-1] == "Egyéb"
    assert len(names) == 19
    income = [r[0] for r in con.execute(
        "SELECT name FROM category WHERE kind='income' ORDER BY sort, id")]
    assert income == ["Fizetés", "Pedikűr", "Egyéb bevétel"]
