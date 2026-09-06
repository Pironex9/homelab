import pytest

from app import migrate
from app.db import Database
from app.services import treatments


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_create_and_list_active(db):
    with db.session() as s:
        treatments.create(s, "Pedikűr", 45, 2500, created_by="1")
        gel = treatments.create(s, "Géllakk", 30, 1800, created_by="1")
        treatments.deactivate(s, gel.id)
    with db.session() as s:
        active = treatments.list_active(s)
        assert [t.name for t in active] == ["Pedikűr"]
        assert len(treatments.list_all(s)) == 2


def test_price_is_stored_as_integer_cents(db):
    with db.session() as s:
        t = treatments.create(s, "Pedikűr", 45, 2500, created_by="1")
        assert t.price_cents == 2500
        assert isinstance(t.price_cents, int)


def test_a_deactivated_treatment_can_come_back(db):
    """A mis-tap on Kivezetés must not need SQL to undo."""
    with db.session() as s:
        t = treatments.create(s, "Pedikűr", 45, 2500, created_by="1")
        treatments.deactivate(s, t.id)
    with db.session() as s:
        assert treatments.list_active(s) == []
        treatments.activate(s, 1)
    with db.session() as s:
        assert [t.name for t in treatments.list_active(s)] == ["Pedikűr"]


def test_an_empty_name_is_refused(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            treatments.create(s, "   ", 45, 2500, created_by="1")


@pytest.mark.parametrize("text,cents", [
    ("25", 2500), ("25,00", 2500), ("25.00", 2500),
    ("18,5", 1850), ("0", 0), (" 12,50 ", 1250), ("25,555", 2556),
])
def test_price_parsing_accepts_what_a_phone_keyboard_produces(text, cents):
    assert treatments.parse_price(text) == cents


@pytest.mark.parametrize("text", [
    "", "abc", "25 EUR", "-5", "1,2,3",
    # Decimal accepts all of these. Without an explicit refusal the comparison
    # signals InvalidOperation or the multiply raises Overflow, and neither is
    # a ValueError, so both escape the route as a 500.
    "nan", "NaN", "snan", "inf", "-inf", "Infinity", "1E999999",
    "1e100", "99999999999999999999",
])
def test_price_parsing_refuses_the_rest(text):
    with pytest.raises(ValueError):
        treatments.parse_price(text)


def test_a_duplicate_name_is_refused_ignoring_case_and_accents(db):
    with db.session() as s:
        treatments.create(s, "Pedikűr", 45, 2500, created_by="1")
        with pytest.raises(ValueError, match="already exists"):
            treatments.create(s, "PEDIKUR", 45, 2500, created_by="1")


def test_a_deactivated_name_can_be_reused(db):
    with db.session() as s:
        t = treatments.create(s, "Pedikűr", 45, 2500, created_by="1")
        treatments.deactivate(s, t.id)
    with db.session() as s:
        treatments.create(s, "Pedikűr", 60, 3000, created_by="1")
        assert len(treatments.list_all(s)) == 2
