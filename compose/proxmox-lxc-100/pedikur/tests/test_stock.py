import pytest

from app import migrate
from app.db import Database
from app.services import products, stock


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


@pytest.fixture
def lakk(db):
    with db.session() as s:
        return products.create(s, "Lakk", "flakon", created_by="1",
                               min_stock=2).id


def test_quantity_is_the_sum_of_the_movements(db, lakk):
    with db.session() as s:
        stock.record(s, lakk, 3, "opening", created_by="1",
                     unit_cost_cents=1200)
        stock.record(s, lakk, 2, "purchase", created_by="1",
                     unit_cost_cents=1300)
        stock.record(s, lakk, -1, "waste", created_by="1")
    with db.session() as s:
        assert stock.quantity(s, lakk) == pytest.approx(4.0)


def test_a_product_with_no_movements_has_no_stock(db, lakk):
    """None from SUM() must not reach a template as None: the level screen
    would render "None flakon" and the below_min comparison would raise."""
    with db.session() as s:
        assert stock.quantity(s, lakk) == 0.0


def test_stock_may_go_negative(db, lakk):
    """Deliberate. Blocking it would mean a "nincs eleg lakk" error in the
    middle of closing a visit with the client in the chair, which is the day
    she stops using the app."""
    with db.session() as s:
        stock.record(s, lakk, -1, "consumption", created_by="1")
    with db.session() as s:
        assert stock.quantity(s, lakk) == pytest.approx(-1.0)


def test_the_level_list_flags_what_is_under_the_minimum(db, lakk):
    with db.session() as s:
        stock.record(s, lakk, 1, "opening", created_by="1")
    with db.session() as s:
        level = stock.levels(s)[0]
        assert level.qty == pytest.approx(1.0)
        assert level.below_min is True


def test_the_level_list_does_not_flag_what_is_exactly_at_the_minimum(db, lakk):
    with db.session() as s:
        stock.record(s, lakk, 2, "opening", created_by="1")
    with db.session() as s:
        assert stock.levels(s)[0].below_min is False


def test_the_level_list_covers_a_product_with_no_movements(db, lakk):
    with db.session() as s:
        levels = stock.levels(s)
        assert len(levels) == 1
        assert levels[0].qty == 0.0


def test_the_cost_to_charge_is_the_price_of_the_last_purchase(db, lakk):
    with db.session() as s:
        stock.record(s, lakk, 3, "opening", created_by="1",
                     unit_cost_cents=1200)
        stock.record(s, lakk, 2, "purchase", created_by="1",
                     unit_cost_cents=1500)
        # An outbound movement must not become the "last known price"
        stock.record(s, lakk, -1, "consumption", created_by="1",
                     unit_cost_cents=1500)
    with db.session() as s:
        assert stock.last_cost_cents(s, lakk) == 1500


def test_the_cost_is_zero_when_nothing_was_ever_bought(db, lakk):
    """Zero, not an exception. A consumption posted at zero cost is a missing
    margin; a raised exception is a failed close."""
    with db.session() as s:
        assert stock.last_cost_cents(s, lakk) == 0


def test_two_purchases_in_one_transaction_break_the_tie_on_id(db, lakk):
    """created_at has one-second resolution, so two movements written inside
    one session share it. Without the id tiebreak the "last" purchase would be
    whichever row SQLite happened to return first."""
    with db.session() as s:
        stock.record(s, lakk, 1, "purchase", created_by="1",
                     unit_cost_cents=1000)
        stock.record(s, lakk, 1, "purchase", created_by="1",
                     unit_cost_cents=1100)
    with db.session() as s:
        assert stock.last_cost_cents(s, lakk) == 1100


def test_a_movement_of_zero_is_refused_before_it_reaches_the_database(db, lakk):
    with db.session() as s:
        with pytest.raises(ValueError):
            stock.record(s, lakk, 0, "correction", created_by="1")


def test_an_invented_reason_is_refused_before_it_reaches_the_database(db, lakk):
    with db.session() as s:
        with pytest.raises(ValueError):
            stock.record(s, lakk, 1, "ajandek", created_by="1")


def test_a_movement_against_a_missing_product_is_a_lookup_error(db):
    """LookupError, not IntegrityError. The foreign key would fire at commit,
    by which time the route has left its try block and the user gets a 500."""
    with db.session() as s:
        with pytest.raises(LookupError):
            stock.record(s, 9999, 1, "purchase", created_by="1")
