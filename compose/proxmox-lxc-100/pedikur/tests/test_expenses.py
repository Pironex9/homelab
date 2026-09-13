import pytest

from app import migrate
from app.db import Database
from app.services import expenses, products, stock


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


@pytest.fixture
def lakk(db):
    with db.session() as s:
        return products.create(s, "Lakk", "flakon", created_by="1").id


def test_an_expense_with_no_lines_is_just_an_expense(db):
    with db.session() as s:
        expenses.create(s, "2026-09-12", "rezsi", 4500, created_by="1",
                        vendor="Aram")
    with db.session() as s:
        rows = expenses.recent(s)
        assert len(rows) == 1
        assert rows[0].amount_cents == 4500
        assert expenses.line_total_cents(s, rows[0].id) == 0


def test_a_line_puts_the_stock_on_the_shelf_at_its_real_price(db, lakk):
    """Buying lacquer is money out and stock in, and it is typed once."""
    with db.session() as s:
        expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                        vendor="Nagyker", lines=[(lakk, 2, 1200)])
    with db.session() as s:
        assert stock.quantity(s, lakk) == 2.0
        assert stock.last_cost_cents(s, lakk) == 1200


def test_the_line_total_is_reported_so_a_mismatch_is_visible(db, lakk):
    """Not refused. She may have bought a coffee on the same receipt, and a
    form that rejects the real receipt is a form she stops filling in."""
    with db.session() as s:
        e = expenses.create(s, "2026-09-12", "anyag", 3000, created_by="1",
                            lines=[(lakk, 2, 1200)])
        e_id = e.id
    with db.session() as s:
        assert expenses.line_total_cents(s, e_id) == 2400


def test_an_invented_category_is_refused(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            expenses.create(s, "2026-09-12", "kave", 300, created_by="1")


def test_a_date_that_is_not_a_calendar_date_is_refused(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            expenses.create(s, "12/09/2026", "anyag", 300, created_by="1")


def test_a_negative_amount_is_refused(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            expenses.create(s, "2026-09-12", "anyag", -300, created_by="1")


def test_a_bad_line_leaves_no_expense_behind(db, lakk):
    """Either the money and the stock both land, or neither does. A recorded
    expense whose line was silently dropped is the worst of the three: nothing
    on any screen would say the stock is short."""
    # pytest.raises outside the session block, the way the route sees it: a
    # caught exception inside one lets the session commit on its way out.
    with pytest.raises(ValueError):
        with db.session() as s:
            expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                            lines=[(lakk, -2, 1200)])
    with db.session() as s:
        assert expenses.recent(s) == []
        assert stock.quantity(s, lakk) == 0.0


def test_a_line_naming_a_product_that_is_gone_leaves_no_expense_behind(db):
    """The guard has to hold even when the caller swallows the exception
    inside its own session block, which is why the lines are checked before
    the expense row is ever added."""
    with db.session() as s:
        with pytest.raises(LookupError):
            expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                            lines=[(9999, 2, 1200)])
    with db.session() as s:
        assert expenses.recent(s) == []


def test_deleting_an_expense_takes_its_stock_back_off_the_shelf(db, lakk):
    """Otherwise the ledger claims two bottles that were never bought, and
    every later consumption is charged at a price that never existed."""
    with db.session() as s:
        e_id = expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                               lines=[(lakk, 2, 1200)]).id
    with db.session() as s:
        expenses.delete(s, e_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, lakk) == 0.0
        assert expenses.recent(s) == []


def test_deleting_is_soft_and_appends_rather_than_erases(db, lakk):
    """The purchase movement stays. Its reversal is another row, because the
    ledger is append-only and a deleted row cannot be audited."""
    from sqlalchemy import select

    from app.models import Expense, StockMovement
    with db.session() as s:
        e_id = expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                               lines=[(lakk, 2, 1200)]).id
    with db.session() as s:
        expenses.delete(s, e_id, created_by="1")
    with db.session() as s:
        assert s.get(Expense, e_id).deleted_at is not None
        rows = list(s.scalars(select(StockMovement)
                              .where(StockMovement.expense_id == e_id)))
        assert sorted(r.reason for r in rows) == ["correction", "purchase"]


def test_deleting_twice_does_not_take_the_stock_off_twice(db, lakk):
    with db.session() as s:
        e_id = expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                               lines=[(lakk, 2, 1200)]).id
    with db.session() as s:
        expenses.delete(s, e_id, created_by="1")
    with db.session() as s:
        expenses.delete(s, e_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, lakk) == 0.0


def test_the_list_is_newest_first(db):
    with db.session() as s:
        expenses.create(s, "2026-08-01", "rezsi", 100, created_by="1")
        expenses.create(s, "2026-09-12", "anyag", 200, created_by="1")
        expenses.create(s, "2026-07-15", "egyeb", 300, created_by="1")
    with db.session() as s:
        assert [e.date for e in expenses.recent(s)] == [
            "2026-09-12", "2026-08-01", "2026-07-15"]
