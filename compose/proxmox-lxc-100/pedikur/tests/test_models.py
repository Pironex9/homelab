"""One row per model against the real migration.

models.py mirrors 001_schema.sql by hand and nothing keeps them in step:
Base.metadata never creates anything. A misspelled column would otherwise ship
and surface as a 500 on whichever screen touches it first.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app import migrate
from app.db import Database
from app.models import (Client, Expense, Product, Setting, StockMovement,
                        Treatment, TreatmentRecipe, User, Visit, VisitItem,
                        WorkingHours)


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_every_model_round_trips(db):
    with db.session() as s:
        s.add(User(name="A", username="a", password_hash="x"))
        s.add(Client(name="Kliens", phone="+421900000000", alert="cukorbeteg",
                     created_by="test", created_at="2026-09-06T10:00:00Z"))
        s.add(Treatment(name="Pedikur", duration_min=60, price_cents=2500,
                        created_by="test"))
        s.flush()
        s.add(Visit(client_id=1, starts_at="2026-09-07T07:00:00Z",
                    ends_at="2026-09-07T08:00:00Z", created_by="test",
                    created_at="2026-09-06T10:00:00Z"))
        s.flush()
        s.add(VisitItem(visit_id=1, kind="treatment", treatment_id=1,
                        qty=1, unit_price_cents=2500))
        s.add(WorkingHours(date="2026-12-24", start="00:00", end="00:00",
                           is_closed=1))
        s.add(Setting(key="test_key", value="test_value"))

    with db.session() as s:
        visit = s.get(Visit, 1)
        assert visit.client.name == "Kliens"
        assert visit.items[0].treatment.name == "Pedikur"
        assert visit.status == "planned"
        assert s.get(Setting, "test_key").value == "test_value"
        assert s.query(WorkingHours).filter_by(is_closed=1).one().end == "00:00"


def test_a_product_starts_with_no_stock_and_no_sale_price(db):
    with db.session() as s:
        p = Product(name="Lakk", unit="flakon", min_stock=2,
                    created_by="1", created_at="2026-09-12T08:00:00Z")
        s.add(p)
        s.flush()
        assert p.sale_price_cents is None
        assert p.archived_at is None


def test_a_movement_of_zero_is_refused(db):
    """A reconcile that decided nothing changed must write no row at all.
    Without this CHECK it would leave a trail of zero rows that look like
    activity and are not."""
    with pytest.raises(IntegrityError):
        with db.session() as s:
            p = Product(name="Lakk", unit="flakon", created_by="1",
                        created_at="2026-09-12T08:00:00Z")
            s.add(p)
            s.flush()
            s.add(StockMovement(product_id=p.id, qty=0, reason="correction",
                                created_by="1",
                                created_at="2026-09-12T08:00:00Z"))


def test_an_invented_movement_reason_is_refused(db):
    with pytest.raises(IntegrityError):
        with db.session() as s:
            p = Product(name="Lakk", unit="flakon", created_by="1",
                        created_at="2026-09-12T08:00:00Z")
            s.add(p)
            s.flush()
            s.add(StockMovement(product_id=p.id, qty=1, reason="ajandek",
                                created_by="1",
                                created_at="2026-09-12T08:00:00Z"))


def test_a_recipe_that_yields_nothing_is_refused(db):
    """Consumption is 1/treatments_per_unit. A zero here is a
    ZeroDivisionError inside the close path, with a client in the chair.

    The treatment is created rather than referenced by a made-up id: with
    PRAGMA foreign_keys = ON a dangling treatment_id raises the same
    IntegrityError, and the test would pass without the CHECK ever firing.
    """
    with pytest.raises(IntegrityError):
        with db.session() as s:
            t = Treatment(name="Pedikur", duration_min=45, price_cents=2500,
                          created_by="1")
            p = Product(name="Lakk", unit="flakon", created_by="1",
                        created_at="2026-09-12T08:00:00Z")
            s.add_all([t, p])
            s.flush()
            s.add(TreatmentRecipe(treatment_id=t.id, product_id=p.id,
                                  treatments_per_unit=0))


def test_an_invented_expense_category_is_refused(db):
    with pytest.raises(IntegrityError):
        with db.session() as s:
            s.add(Expense(date="2026-09-12", category="kave",
                          amount_cents=500, created_by="1",
                          created_at="2026-09-12T08:00:00Z"))


def test_an_expense_date_has_to_be_a_calendar_date(db):
    with pytest.raises(IntegrityError):
        with db.session() as s:
            s.add(Expense(date="2026-09-12T08:00:00Z", category="anyag",
                          amount_cents=500, created_by="1",
                          created_at="2026-09-12T08:00:00Z"))
