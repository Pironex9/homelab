import pytest

from app import migrate
from app.db import Database
from app.services import products, recipes, treatments


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


@pytest.fixture
def ids(db):
    with db.session() as s:
        t = treatments.create(s, "Pedikur", 45, 2500, created_by="1")
        p = products.create(s, "Lakk", "flakon", created_by="1")
        return t.id, p.id


def test_a_recipe_is_stored_and_read_back(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        recipes.set_for(s, treatment_id, product_id, 30)
    with db.session() as s:
        rows = recipes.for_treatment(s, treatment_id)
        assert len(rows) == 1
        assert rows[0].treatments_per_unit == 30
        assert rows[0].product.name == "Lakk"


def test_setting_the_same_pair_twice_updates_rather_than_duplicates(db, ids):
    """Two rows for one pair would double that treatment's consumption, and
    nothing downstream would say why the lacquer runs out twice as fast."""
    treatment_id, product_id = ids
    with db.session() as s:
        recipes.set_for(s, treatment_id, product_id, 30)
        recipes.set_for(s, treatment_id, product_id, 20)
    with db.session() as s:
        rows = recipes.for_treatment(s, treatment_id)
        assert len(rows) == 1
        assert rows[0].treatments_per_unit == 20


def test_a_yield_of_zero_is_refused(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        with pytest.raises(ValueError):
            recipes.set_for(s, treatment_id, product_id, 0)


def test_a_negative_yield_is_refused(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        with pytest.raises(ValueError):
            recipes.set_for(s, treatment_id, product_id, -5)


def test_removing_a_recipe_leaves_the_treatment_alone(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        row = recipes.set_for(s, treatment_id, product_id, 30)
        recipes.remove(s, row.id)
    with db.session() as s:
        assert recipes.for_treatment(s, treatment_id) == []
        assert len(treatments.list_all(s)) == 1


def test_by_treatment_groups_every_recipe_in_one_query(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        other = products.create(s, "Gel", "flakon", created_by="1")
        recipes.set_for(s, treatment_id, product_id, 30)
        recipes.set_for(s, treatment_id, other.id, 10)
    with db.session() as s:
        grouped = recipes.by_treatment(s)
        assert sorted(r.product.name for r in grouped[treatment_id]) == ["Gel", "Lakk"]


def test_a_treatment_with_no_recipe_is_absent_rather_than_empty(db, ids):
    """Callers use `.get(id, [])`. An empty list stored for every treatment
    would hide the difference between "no recipe yet" and "a recipe of
    nothing", and only the first one is normal."""
    treatment_id, _ = ids
    with db.session() as s:
        assert treatment_id not in recipes.by_treatment(s)


def test_removing_a_recipe_that_is_already_gone_is_a_lookup_error(db, ids):
    with db.session() as s:
        with pytest.raises(LookupError):
            recipes.remove(s, 9999)
