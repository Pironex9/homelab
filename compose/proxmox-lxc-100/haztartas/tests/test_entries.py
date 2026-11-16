from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app import fx, migrate
from app.db import Database
from app.models import Category, Entry, User, Wallet
from app.services.entries import (
    EntryInput, NeedsRate, NotAllowed, create_entry, delete_entry,
    find_duplicates, reveal_entry, top_up, update_entry,
)


@pytest.fixture
def s(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    db = Database(db_path)
    with db.session() as session:
        fx.store(session, [("2026-11-10", "HUF", Decimal("400")),
                           ("2026-11-12", "HUF", Decimal("500"))])
        yield session


def _user(s, username, role):
    u = User(name=username.title(), username=username, role=role,
             password_hash="x")
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


def cat(s, name, kind):
    return s.scalars(select(Category).where(
        Category.name == name, Category.kind == kind)).one().id


def inp(wallet, **kw):
    base = dict(wallet_id=wallet.id, kind="expense", date="2026-11-10",
                amount_minor=3200, currency="EUR", category_id=None,
                merchant="Lidl", note=None, payment="card", hidden=False,
                reveal_on=None)
    base.update(kw)
    return EntryInput(**base)


def test_create_is_idempotent_on_client_uuid(s, adult, household):
    a = create_entry(s, adult, inp(household, client_uuid="u1"))
    b = create_entry(s, adult, inp(household, client_uuid="u1", amount_minor=9))
    assert a.id == b.id and b.amount_minor == 3200
    assert s.scalar(select(func.count()).select_from(Entry)) == 1


def test_client_uuid_of_another_author_not_handed_out(s, adult, adult2, household):
    create_entry(s, adult, inp(household, client_uuid="u1"))
    with pytest.raises(NotAllowed):
        create_entry(s, adult2, inp(household, client_uuid="u1"))


def test_child_cannot_add_household_income(s, child, household):
    with pytest.raises(NotAllowed):
        create_entry(s, child, inp(household, kind="income"))
    create_entry(s, child, inp(household))   # child expense is fine


def test_adult_cannot_add_expense_to_child_wallet(s, adult, cwallet):
    with pytest.raises(NotAllowed):
        create_entry(s, adult, inp(cwallet))
    create_entry(s, adult, inp(cwallet, kind="income", merchant=None))


def test_nobody_adds_to_another_childs_wallet(s, child, adult, cwallet):
    other = _user(s, "dani", "child")
    with pytest.raises(NotAllowed):
        create_entry(s, other, inp(cwallet))


def test_child_can_add_income_to_own_wallet(s, child, cwallet):
    e = create_entry(s, child, inp(cwallet, kind="income"))
    assert e.kind == "income" and e.created_by == child.id
    create_entry(s, child, inp(cwallet))


def test_huf_entry_gets_eur_at_save(s, adult, household):
    e = create_entry(s, adult, inp(household, currency="HUF", amount_minor=40000))
    assert e.eur_minor == 100 and e.fx_rate == "400"


def test_unknown_currency_needs_rate(s, adult, household):
    with pytest.raises(NeedsRate):
        create_entry(s, adult, inp(household, currency="PLN"))


def test_manual_rate_used(s, adult, household):
    e = create_entry(s, adult, inp(household, currency="PLN", amount_minor=430,
                                   manual_rate=Decimal("4.3")))
    assert e.eur_minor == 100 and e.fx_rate == "4.3"


def test_update_recomputes_eur_when_date_changes(s, adult, household):
    e = create_entry(s, adult, inp(household, currency="HUF", amount_minor=40000))
    assert e.eur_minor == 100
    u = update_entry(s, adult, e.id, inp(household, currency="HUF",
                                         amount_minor=40000, date="2026-11-12"))
    assert u.eur_minor == 80 and u.fx_rate == "500" and u.updated_at


def test_update_keeps_eur_when_nothing_money_changes(s, adult, household):
    e = create_entry(s, adult, inp(household, currency="HUF", amount_minor=40000))
    fx.store(s, [("2026-11-10", "HUF", Decimal("999"))])
    u = update_entry(s, adult, e.id, inp(household, currency="HUF",
                                         amount_minor=40000, merchant="Tesco"))
    assert u.eur_minor == 100 and u.merchant == "Tesco"


def test_update_others_secret_not_allowed(s, adult, adult2, household):
    e = create_entry(s, adult, inp(household, hidden=True))
    with pytest.raises(NotAllowed):
        update_entry(s, adult2, e.id, inp(household))
    with pytest.raises(NotAllowed):
        delete_entry(s, adult2, e.id)


def test_delete_top_up_removes_both(s, adult, child, household, cwallet):
    a, b = top_up(s, adult, cwallet.id, 500, "EUR", "2026-11-10")
    assert a.transfer_group == b.transfer_group
    assert (a.wallet_id, a.kind) == (household.id, "expense")
    assert (b.wallet_id, b.kind) == (cwallet.id, "income")
    assert a.category_id == cat(s, "Zsebpénz", "expense")
    assert b.category_id == cat(s, "Egyéb bevétel", "income")
    with pytest.raises(NotAllowed):
        update_entry(s, adult, a.id, inp(household))
    delete_entry(s, adult, a.id)
    assert a.deleted_at and b.deleted_at


def test_top_up_requires_adult_and_child_wallet(s, adult, child, household,
                                                cwallet):
    with pytest.raises(NotAllowed):
        top_up(s, child, cwallet.id, 500, "EUR", "2026-11-10")
    with pytest.raises(NotAllowed):
        top_up(s, adult, household.id, 500, "EUR", "2026-11-10")


def test_reveal_by_non_author_not_allowed(s, adult, adult2, household):
    e = create_entry(s, adult, inp(household, hidden=True))
    with pytest.raises(NotAllowed):
        reveal_entry(s, adult2, e.id)
    reveal_entry(s, adult, e.id)
    assert e.hidden == 0


def test_duplicate_found_within_2_percent_and_yesterday(s, adult, adult2,
                                                        household):
    old = create_entry(s, adult, inp(household, date="2026-11-09"))
    hints = find_duplicates(s, adult2, inp(household, date="2026-11-10",
                                           amount_minor=3250))
    assert [h.entry_id for h in hints] == [old.id]
    h = hints[0]
    assert (h.merchant, h.author_name, h.eur_minor, h.hidden) == (
        "Lidl", "Anna", 3200, False)
    assert find_duplicates(s, adult2, inp(household, amount_minor=3400)) == []


def test_duplicate_excludes_edited_entry(s, adult, household):
    e = create_entry(s, adult, inp(household))
    assert find_duplicates(s, adult, inp(household)) != []
    assert find_duplicates(s, adult, inp(household), exclude_id=e.id) == []


def test_duplicate_without_rate_returns_empty(s, adult, household):
    assert find_duplicates(s, adult, inp(household, currency="PLN")) == []


def test_duplicate_not_found_two_days_back(s, adult, household):
    create_entry(s, adult, inp(household, date="2026-11-08"))
    assert find_duplicates(s, adult, inp(household, date="2026-11-10")) == []


def test_duplicate_hint_hides_secret_merchant(s, adult, adult2, household):
    create_entry(s, adult, inp(household, hidden=True, merchant="Ring"))
    [h] = find_duplicates(s, adult2, inp(household))
    assert h.merchant is None and h.hidden is True and h.created_at is None


def test_child_never_gets_hint_about_adult_entries(s, adult, child, household):
    create_entry(s, adult, inp(household))
    assert find_duplicates(s, child, inp(household)) == []


@pytest.mark.parametrize("change", [
    dict(kind="loan"), dict(payment="bitcoin"), dict(currency="eur"),
    dict(currency="EURO"), dict(amount_minor=0), dict(amount_minor=-5),
    dict(date="2026-13-01"), dict(date="10.11.2026"), dict(category_id=9999),
    dict(reveal_on="2026-12-01"), dict(category_id="income"),
    dict(hidden=True, reveal_on="soon"),
])
def test_invalid_input_is_value_error(s, adult, household, change):
    if change.get("category_id") == "income":
        change["category_id"] = cat(s, "Fizetés", "income")   # kind mismatch
    with pytest.raises(ValueError):
        create_entry(s, adult, inp(household, **change))


def test_non_author_cannot_change_hidden_flags(s, adult, adult2, household):
    e = create_entry(s, adult, inp(household))
    with pytest.raises(NotAllowed):
        update_entry(s, adult2, e.id, inp(household, hidden=True))
    u = update_entry(s, adult2, e.id, inp(household, merchant="Tesco"))
    assert u.hidden == 0 and u.merchant == "Tesco"
    f = create_entry(s, adult, inp(household, hidden=True, reveal_on="2026-01-01"))
    with pytest.raises(NotAllowed):   # revealed: editable, flags not
        update_entry(s, adult2, f.id, inp(household, hidden=True,
                                          reveal_on="2026-02-02"))
    u = update_entry(s, adult2, f.id, inp(household, hidden=True,
                                          reveal_on="2026-01-01", note="x"))
    assert u.note == "x" and u.reveal_on == "2026-01-01"


def test_duplicate_hint_not_hidden_after_reveal_on_passes(s, adult, adult2,
                                                          household):
    create_entry(s, adult, inp(household, hidden=True, reveal_on="2026-01-01"))
    [h] = find_duplicates(s, adult2, inp(household))
    assert h.hidden is False and h.merchant == "Lidl" and h.created_at


def test_archived_category_ok_on_update_unless_changed(s, adult, household):
    c = cat(s, "Egyéb", "expense")
    e = create_entry(s, adult, inp(household, category_id=c))
    s.get(Category, c).archived_at = "2026-11-01T00:00:00Z"
    update_entry(s, adult, e.id, inp(household, category_id=c, merchant="Tesco"))
    other = cat(s, "Ruha", "expense")
    s.get(Category, other).archived_at = "2026-11-01T00:00:00Z"
    with pytest.raises(ValueError):
        update_entry(s, adult, e.id, inp(household, category_id=other))
    with pytest.raises(ValueError):
        create_entry(s, adult, inp(household, category_id=c))


@pytest.mark.parametrize("rate", ["NaN", "Infinity", "-Infinity", "0", "-1"])
def test_non_finite_manual_rate_is_value_error(s, adult, household, rate):
    with pytest.raises(ValueError):
        create_entry(s, adult, inp(household, currency="PLN",
                                   manual_rate=Decimal(rate)))
