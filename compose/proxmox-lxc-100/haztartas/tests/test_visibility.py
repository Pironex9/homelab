import pytest
from sqlalchemy import func, select

from app import migrate
from app.db import Database
from app.models import Entry, User, Wallet
from app.services.visibility import (
    RedactedEntry, can_edit, is_secret, listable, present, text_searchable,
    view_of,
)

TODAY = "2026-11-15"


@pytest.fixture
def s(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    db = Database(db_path)
    with db.session() as session:
        yield session


def _user(s, username, role):
    u = User(name=username, username=username, role=role, password_hash="x")
    s.add(u)
    s.flush()
    return u


@pytest.fixture
def adult(s):
    return _user(s, "anna", "adult")


@pytest.fixture
def adult2(s):
    return _user(s, "bela", "adult")


@pytest.fixture
def child(s):
    return _user(s, "cili", "child")


@pytest.fixture
def household(s):
    return s.scalars(select(Wallet).where(Wallet.owner_user_id.is_(None))).one()


@pytest.fixture
def cwallet(s, child):
    w = Wallet(name="Cili", owner_user_id=child.id)
    s.add(w)
    s.flush()
    return w


def add_entry(s, author, wallet=None, *, merchant="Bolt", hidden=False,
              reveal_on=None, deleted_at=None, transfer_group=None,
              amount_minor=1000):
    if wallet is None:
        wallet = s.scalars(
            select(Wallet).where(Wallet.owner_user_id.is_(None))).one()
    e = Entry(
        wallet_id=wallet.id, kind="expense", status="confirmed",
        date="2026-11-10", merchant=merchant, amount_minor=amount_minor,
        currency="EUR", eur_minor=amount_minor, fx_rate="1", payment="card",
        hidden=1 if hidden else 0, reveal_on=reveal_on, source="manual",
        created_by=author.id, created_at="2026-11-10T10:00:00Z",
        deleted_at=deleted_at, transfer_group=transfer_group)
    s.add(e)
    s.flush()
    return e


def check(viewer, e, w, view, edit):
    assert view_of(viewer, e, w, TODAY) == view
    assert can_edit(viewer, e, w, TODAY) is edit


# --- is_secret

@pytest.mark.parametrize("hidden,reveal_on,expected", [
    (False, None, False),
    (False, "2030-01-01", False),
    (True, None, True),
    (True, "2026-11-16", True),
    (True, "2026-11-15", False),
    (True, "2026-11-14", False),
])
def test_is_secret(s, adult, hidden, reveal_on, expected):
    e = add_entry(s, adult, hidden=hidden, reveal_on=reveal_on)
    assert is_secret(e, TODAY) is expected


# --- table rows, top to bottom

def test_transfer_group_cannot_be_edited_by_anyone(s, adult, adult2, child,
                                                   household, cwallet):
    e = add_entry(s, adult, household, transfer_group="g1")
    check(adult, e, household, "full", False)      # even the author
    check(adult2, e, household, "full", False)
    t = add_entry(s, adult, cwallet, transfer_group="g1")
    check(child, t, cwallet, "full", False)        # view rows below still apply
    check(adult2, t, cwallet, "full", False)


def test_transfer_group_row_continues_to_rows_below(s, adult, adult2, child,
                                                    household):
    e = add_entry(s, adult, household, transfer_group="g1", hidden=True)
    check(adult2, e, household, "redacted", False)
    check(child, e, household, "none", False)


def test_author_sees_and_edits_own(s, adult, child, household, cwallet):
    check(adult, add_entry(s, adult, household), household, "full", True)
    check(adult, add_entry(s, adult, household, hidden=True), household,
          "full", True)
    check(child, add_entry(s, child, household), household, "full", True)
    check(child, add_entry(s, child, household, hidden=True), household,
          "full", True)


def test_child_in_own_wallet_by_child_is_full_and_editable(s, child, cwallet):
    check(child, add_entry(s, child, cwallet), cwallet, "full", True)


def test_adult_secret_not_author_redacted(s, adult, adult2, household):
    e = add_entry(s, adult2, household, hidden=True)
    check(adult, e, household, "redacted", False)


def test_adult_not_secret_full_and_editable(s, adult, adult2, child, household,
                                            cwallet):
    check(adult, add_entry(s, adult2, household), household, "full", True)
    check(adult, add_entry(s, child, household), household, "full", True)
    check(adult, add_entry(s, child, cwallet), cwallet, "full", True)
    check(adult, add_entry(s, adult2, household, hidden=True,
                           reveal_on="2026-11-01"), household, "full", True)


def test_child_entry_not_by_child_not_in_wallet_is_none(s, adult, child,
                                                        household):
    check(child, add_entry(s, adult, household), household, "none", False)


def test_child_topup_in_own_wallet_by_adult_full_not_editable(s, adult, child,
                                                              cwallet):
    check(child, add_entry(s, adult, cwallet), cwallet, "full", False)


def test_child_cannot_see_secret_adult_entry_in_own_wallet(s, adult, child,
                                                           cwallet):
    check(child, add_entry(s, adult, cwallet, hidden=True), cwallet,
          "none", False)


def test_reveal_on_today_is_full(s, adult, adult2, household):
    e = add_entry(s, adult2, household, hidden=True, reveal_on=TODAY)
    check(adult, e, household, "full", True)


def test_reveal_on_tomorrow_is_redacted(s, adult, adult2, household):
    e = add_entry(s, adult2, household, hidden=True, reveal_on="2026-11-16")
    check(adult, e, household, "redacted", False)


def test_child_hidden_entry_redacted_for_adult(s, adult, child, household,
                                               cwallet):
    check(adult, add_entry(s, child, household, hidden=True), household,
          "redacted", False)
    check(adult, add_entry(s, child, cwallet, hidden=True), cwallet,
          "redacted", False)


def test_deleted_entry_is_none_and_not_editable(s, adult, adult2, child,
                                                household):
    e = add_entry(s, adult, household, deleted_at="2026-11-12T00:00:00Z")
    check(adult, e, household, "none", False)      # even the author
    check(adult2, e, household, "none", False)
    check(child, e, household, "none", False)


# --- present / RedactedEntry

def test_present_maps_each_view(s, adult, adult2, child, household):
    secret = add_entry(s, adult2, household, hidden=True, merchant="Parfüm")
    r = present(adult, secret, household, TODAY)
    assert isinstance(r, RedactedEntry)
    assert r == RedactedEntry(
        id=secret.id, amount_minor=1000, currency="EUR", eur_minor=1000,
        category_id=None, date="2026-11-10", created_by=adult2.id, hidden=True)
    assert not hasattr(r, "merchant")
    assert "Parfüm" not in repr(r)
    plain = add_entry(s, adult2, household)
    assert present(adult, plain, household, TODAY) is plain
    assert present(child, plain, household, TODAY) is None


def test_redacted_entry_has_exactly_the_allowed_fields():
    from dataclasses import fields
    assert [f.name for f in fields(RedactedEntry)] == [
        "id", "amount_minor", "currency", "eur_minor", "category_id", "date",
        "created_by", "hidden"]
    with pytest.raises(Exception):
        RedactedEntry(1, 1, "EUR", 1, None, "d", 1, True).hidden = False


# --- SQL filters

def _ids(s, viewer, *extra):
    return set(s.scalars(select(Entry.id).join(Wallet).where(
        listable(viewer, TODAY), *extra)).all())


def test_listable_child_sees_only_own_and_wallet(s, adult, adult2, child,
                                                 household, cwallet):
    own = add_entry(s, child, household)
    own_hidden = add_entry(s, child, household, hidden=True)
    in_wallet_by_child = add_entry(s, child, cwallet)
    topup = add_entry(s, adult, cwallet)
    secret_in_wallet = add_entry(s, adult, cwallet, hidden=True)
    revealed_in_wallet = add_entry(s, adult, cwallet, hidden=True,
                                   reveal_on=TODAY)
    add_entry(s, adult, household)
    add_entry(s, adult2, household, hidden=True)
    assert _ids(s, child) == {own.id, own_hidden.id, in_wallet_by_child.id,
                              topup.id, revealed_in_wallet.id}
    assert secret_in_wallet.id not in _ids(s, child)


def test_listable_adult_sees_everything_not_deleted(s, adult, adult2, child,
                                                    household, cwallet):
    es = [add_entry(s, adult2, household), add_entry(s, child, cwallet),
          add_entry(s, child, household, hidden=True),
          add_entry(s, adult2, household, hidden=True)]
    add_entry(s, adult, household, deleted_at="2026-11-12T00:00:00Z")
    assert _ids(s, adult) == {e.id for e in es}


def test_listable_excludes_deleted(s, adult, child, household):
    gone = add_entry(s, adult, household, deleted_at="2026-11-12T00:00:00Z")
    gone_c = add_entry(s, child, household, deleted_at="2026-11-12T00:00:00Z")
    assert gone.id not in _ids(s, adult)
    assert gone_c.id not in _ids(s, child)


def test_listable_agrees_with_view_of(s, adult, adult2, child, household,
                                      cwallet):
    for author in (adult, adult2, child):
        for wallet in (household, cwallet):
            for hidden, reveal in ((False, None), (True, None),
                                   (True, TODAY), (True, "2026-11-16")):
                add_entry(s, author, wallet, hidden=hidden, reveal_on=reveal)
    wallets = {w.id: w for w in s.scalars(select(Wallet))}
    for viewer in (adult, adult2, child):
        expected = {e.id for e in s.scalars(select(Entry))
                    if view_of(viewer, e, wallets[e.wallet_id], TODAY) != "none"}
        assert _ids(s, viewer) == expected


def test_search_never_matches_others_hidden_text(s, adult, adult2):
    add_entry(s, adult2, merchant="Parfümória", hidden=True)
    rows = s.scalars(select(Entry).join(Wallet)
        .where(listable(adult, TODAY), text_searchable(adult, TODAY),
               func.fold(Entry.merchant).contains("parfum"))).all()
    assert rows == []


def test_search_matches_own_hidden_and_others_visible_text(s, adult, adult2):
    mine = add_entry(s, adult, merchant="Parfümória", hidden=True)
    other = add_entry(s, adult2, merchant="Parfümária")
    revealed = add_entry(s, adult2, merchant="Parfümöria", hidden=True,
                         reveal_on=TODAY)
    rows = s.scalars(select(Entry.id).join(Wallet)
        .where(listable(adult, TODAY), text_searchable(adult, TODAY),
               func.fold(Entry.merchant).contains("parfum"))).all()
    assert set(rows) == {mine.id, other.id, revealed.id}
