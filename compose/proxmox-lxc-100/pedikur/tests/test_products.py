import pytest

from app import migrate
from app.db import Database
from app.services import products


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_create_and_list(db):
    with db.session() as s:
        products.create(s, "Lakk", "flakon", created_by="1", min_stock=2)
        products.create(s, "Kesztyu", "doboz", created_by="1")
    with db.session() as s:
        assert [p.name for p in products.list_all(s)] == ["Kesztyu", "Lakk"]


def test_archived_products_are_out_unless_asked_for(db):
    with db.session() as s:
        gone = products.create(s, "Regi lakk", "flakon", created_by="1")
        products.create(s, "Lakk", "flakon", created_by="1")
        products.archive(s, gone.id)
    with db.session() as s:
        assert [p.name for p in products.list_all(s)] == ["Lakk"]
        assert len(products.list_all(s, include_archived=True)) == 2


def test_unarchive_brings_it_back(db):
    with db.session() as s:
        p = products.create(s, "Lakk", "flakon", created_by="1")
        products.archive(s, p.id)
        products.unarchive(s, p.id)
    with db.session() as s:
        assert [p.name for p in products.list_all(s)] == ["Lakk"]


def test_only_products_with_a_sale_price_are_for_sale(db):
    with db.session() as s:
        products.create(s, "Lakk", "flakon", created_by="1")
        products.create(s, "Krem", "tubus", created_by="1",
                        sale_price_cents=850)
    with db.session() as s:
        assert [p.name for p in products.for_sale(s)] == ["Krem"]


def test_an_archived_product_is_never_for_sale(db):
    with db.session() as s:
        p = products.create(s, "Krem", "tubus", created_by="1",
                            sale_price_cents=850)
        products.archive(s, p.id)
    with db.session() as s:
        assert products.for_sale(s) == []


def test_a_product_needs_a_name_and_a_unit(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            products.create(s, "   ", "flakon", created_by="1")
        with pytest.raises(ValueError):
            products.create(s, "Lakk", "  ", created_by="1")


def test_update_refuses_a_field_that_is_not_on_the_whitelist(db):
    """Field names reach update from a form. Without the whitelist,
    ?created_by=... or ?id=... would be an accepted write."""
    with db.session() as s:
        p = products.create(s, "Lakk", "flakon", created_by="1")
        with pytest.raises(ValueError):
            products.update(s, p.id, created_by="2")
