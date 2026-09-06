import pytest

from app import migrate
from app.db import Database
from app.services import clients


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_search_is_case_insensitive_and_partial(db):
    with db.session() as s:
        clients.create(s, "Kovács Anna", "0900111222", created_by="1")
        clients.create(s, "Nagy Béla", None, created_by="1")
    with db.session() as s:
        assert [c.name for c in clients.search(s, "kovács")] == ["Kovács Anna"]
        assert [c.name for c in clients.search(s, "an")] == ["Kovács Anna"]
        assert clients.search(s, "zzz") == []


def test_search_ignores_accents_in_both_directions(db):
    """She types on a phone keyboard. Requiring the accents to match would
    mean "kovacs" finds nothing, and SQLite's LIKE folds ASCII only."""
    with db.session() as s:
        clients.create(s, "Kovács Anna", None, created_by="1")
        clients.create(s, "Tóth Örs", None, created_by="1")
    with db.session() as s:
        assert [c.name for c in clients.search(s, "kovacs")] == ["Kovács Anna"]
        assert [c.name for c in clients.search(s, "KOVÁCS")] == ["Kovács Anna"]
        assert [c.name for c in clients.search(s, "ors")] == ["Tóth Örs"]
        assert [c.name for c in clients.search(s, "őrs")] == ["Tóth Örs"]


def test_search_treats_like_wildcards_as_text(db):
    with db.session() as s:
        clients.create(s, "Kovács Anna", None, created_by="1")
    with db.session() as s:
        assert clients.search(s, "%") == []
        assert clients.search(s, "_") == []


def test_archived_clients_are_hidden_from_search(db):
    with db.session() as s:
        c = clients.create(s, "Kovács Anna", None, created_by="1")
        clients.archive(s, c.id)
    with db.session() as s:
        assert clients.search(s, "kovács") == []
        assert clients.get(s, 1) is not None   # still reachable by id


def test_alert_is_stored_but_never_returned_by_search_projection(db):
    with db.session() as s:
        clients.create(s, "Kovács Anna", None, created_by="1",
                       alert="cukorbeteg")
    with db.session() as s:
        found = clients.search(s, "kovács")[0]
        assert found.has_alert is True
        # the wording must not leave the service: a list screen never shows it
        assert not hasattr(found, "alert")


def test_a_blank_alert_does_not_light_the_dot(db):
    with db.session() as s:
        clients.create(s, "Kovács Anna", None, created_by="1", alert="   ")
    with db.session() as s:
        assert clients.search(s, "kovács")[0].has_alert is False


def test_an_empty_name_is_refused(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            clients.create(s, "  ", None, created_by="1")


def test_history_is_empty_until_a_visit_is_closed(db):
    with db.session() as s:
        c = clients.create(s, "Kovács Anna", None, created_by="1")
    with db.session() as s:
        assert clients.history(s, c.id) == []


def test_the_list_sorts_accented_names_where_a_reader_expects_them(db):
    """SQLite's BINARY collation puts every accented initial after Z."""
    with db.session() as s:
        for name in ("Zsolt", "Ádám", "Kovács Anna"):
            clients.create(s, name, None, created_by="1")
    with db.session() as s:
        assert [c.name for c in clients.search(s, "")] == [
            "Ádám", "Kovács Anna", "Zsolt"]


def test_update_refuses_a_field_that_is_not_a_column(db):
    """setattr succeeds for any name and flush reports success, so a typo in
    an Erase would be a GDPR request silently not honoured."""
    with db.session() as s:
        clients.create(s, "Kovács Anna", None, created_by="1")
        with pytest.raises(ValueError, match="not columns of client"):
            clients.update(s, 1, erase_at="2026-09-06T10:00:00Z")


def test_erased_clients_are_hidden_like_archived_ones(db):
    with db.session() as s:
        clients.create(s, "Kovács Anna", None, created_by="1")
        clients.update(s, 1, erased_at="2026-09-06T10:00:00Z")
    with db.session() as s:
        assert clients.search(s, "") == []
