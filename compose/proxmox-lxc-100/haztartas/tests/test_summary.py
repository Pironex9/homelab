import pytest
from decimal import Decimal
from sqlalchemy import select

from app import fx, migrate
from app.db import Database
from app.models import Category, Recurring, User, Wallet
from app.services.entries import EntryInput, create_entry, top_up
from app.services.summary import month_summary, wallet_balance

M = "2026-11"
TODAY = "2026-11-15"


@pytest.fixture
def s(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    db = Database(db_path)
    with db.session() as session:
        fx.store(session, [("2026-11-10", "HUF", Decimal("400"))])
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


def cat(s, name, kind="expense"):
    return s.scalars(select(Category).where(
        Category.name == name, Category.kind == kind)).one()


def inp(wallet, **kw):
    base = dict(wallet_id=wallet.id, kind="expense", date="2026-11-10",
                amount_minor=1000, currency="EUR", category_id=None,
                merchant="Lidl", note=None, payment="card", hidden=False,
                reveal_on=None)
    base.update(kw)
    return EntryInput(**base)


def line(summary, name):
    return next(c for c in summary.categories if c.name == name)


def test_secret_entry_counts_in_category(s, adult, adult2, household):
    food = cat(s, "Élelmiszer")
    create_entry(s, adult, inp(household, category_id=food.id))
    create_entry(s, adult2, inp(household, category_id=food.id,
                                amount_minor=500, hidden=True))
    r = month_summary(s, M, TODAY)
    assert line(r, "Élelmiszer").spent_eur_minor == 1500
    assert r.expense_eur_minor == 1500


def test_child_wallet_not_in_household_totals(s, adult, child, household,
                                              cwallet):
    create_entry(s, adult, inp(cwallet, kind="income", merchant=None,
                               amount_minor=700))
    create_entry(s, child, inp(cwallet, amount_minor=300))
    r = month_summary(s, M, TODAY)
    assert (r.income_eur_minor, r.expense_eur_minor, r.balance_eur_minor) == (
        0, 0, 0)
    assert r.by_author == []


def test_top_up_counts_once_as_zsebpenz(s, adult, household, cwallet):
    top_up(s, adult, cwallet.id, 2000, "EUR", "2026-11-10")
    r = month_summary(s, M, TODAY)
    assert line(r, "Zsebpénz").spent_eur_minor == 2000
    assert r.expense_eur_minor == 2000 and r.income_eur_minor == 0


def test_drafts_and_deleted_excluded(s, adult, household):
    from app.services.entries import delete_entry
    food = cat(s, "Élelmiszer")
    create_entry(s, adult, inp(household, category_id=food.id), status="draft")
    gone = create_entry(s, adult, inp(household, category_id=food.id,
                                      amount_minor=200))
    delete_entry(s, adult, gone.id)
    create_entry(s, adult, inp(household, category_id=food.id,
                               amount_minor=50))
    r = month_summary(s, M, TODAY)
    assert r.expense_eur_minor == 50
    assert line(r, "Élelmiszer").spent_eur_minor == 50


def test_month_boundary_31st_in_month(s, adult, household):
    food = cat(s, "Élelmiszer")
    for d, amt in (("2026-10-31", 1), ("2026-11-01", 10), ("2026-11-30", 100),
                   ("2026-12-01", 1000)):
        create_entry(s, adult, inp(household, category_id=food.id, date=d,
                                   amount_minor=amt, currency="EUR"))
    assert month_summary(s, M, TODAY).expense_eur_minor == 110
    assert month_summary(s, "2026-10", TODAY).expense_eur_minor == 1


def test_expected_income_disappears_when_confirmed(s, adult, household):
    pay = cat(s, "Fizetés", "income")
    r1 = Recurring(name="Fizetes A", kind="income", category_id=pay.id,
                   amount_minor=200000, currency="EUR", day_of_month=15)
    r2 = Recurring(name="Fizetes B", kind="income", category_id=pay.id,
                   amount_minor=100000, currency="EUR", day_of_month=10)
    r3 = Recurring(name="Regi", kind="income", category_id=pay.id,
                   amount_minor=1, currency="EUR", day_of_month=5,
                   archived_at="2026-01-01T00:00:00Z")
    s.add_all([r1, r2, r3])
    s.flush()
    r = month_summary(s, M, TODAY)
    assert [(e.name, e.day) for e in r.expected] == [
        ("Fizetes B", "2026-11-10"), ("Fizetes A", "2026-11-15")]
    # a pending draft still counts as expected
    d = create_entry(s, adult, inp(household, kind="income", category_id=pay.id,
                                   amount_minor=200000), status="draft")
    d.recurring_id, d.recurring_month = r1.id, M
    s.flush()
    assert len(month_summary(s, M, TODAY).expected) == 2
    d.status = "confirmed"
    s.flush()
    r = month_summary(s, M, TODAY)
    assert [e.name for e in r.expected] == ["Fizetes B"]
    assert r.income_eur_minor == 200000
    # other month unaffected
    assert len(month_summary(s, "2026-12", TODAY).expected) == 2


def test_wallet_balance_after_top_up_and_spend(s, adult, child, household,
                                               cwallet):
    top_up(s, adult, cwallet.id, 2000, "EUR", "2026-11-10")
    create_entry(s, child, inp(cwallet, amount_minor=450))
    assert wallet_balance(s, cwallet.id, child, TODAY) == 1550
    assert wallet_balance(s, cwallet.id, adult, TODAY) == 1550


def test_child_balance_excludes_adult_secret_gift(s, adult, child, cwallet):
    create_entry(s, adult, inp(cwallet, kind="income", merchant=None,
                               amount_minor=1000, hidden=True,
                               reveal_on="2026-12-24"))
    assert wallet_balance(s, cwallet.id, child, TODAY) == 0
    assert wallet_balance(s, cwallet.id, adult, TODAY) == 1000
    assert wallet_balance(s, cwallet.id, child, "2026-12-24") == 1000
    assert wallet_balance(s, cwallet.id, adult, "2026-12-24") == 1000


def test_by_author_sorted_desc(s, adult, adult2, household):
    create_entry(s, adult, inp(household, amount_minor=100))
    create_entry(s, adult2, inp(household, amount_minor=300))
    create_entry(s, adult, inp(household, amount_minor=100))
    assert month_summary(s, M, TODAY).by_author == [("Bela", 300), ("Anna", 200)]


def test_categories_limit_archived_and_order(s, adult, household):
    food, rezsi, ruha = (cat(s, n) for n in ("Élelmiszer", "Rezsi", "Ruha"))
    rezsi.monthly_limit_eur_minor = 9000     # limit, no spending: listed
    ruha.archived_at = "2026-01-01T00:00:00Z"
    create_entry(s, adult, inp(household, category_id=food.id))
    s.flush()
    r = month_summary(s, M, TODAY)
    assert [(c.name, c.spent_eur_minor, c.limit_eur_minor)
            for c in r.categories] == [("Élelmiszer", 1000, None),
                                       ("Rezsi", 0, 9000)]
    # archived with spending in the month: history must add up
    ruha.archived_at = None
    create_entry(s, adult, inp(household, category_id=ruha.id, amount_minor=70))
    ruha.archived_at = "2026-11-12T00:00:00Z"
    s.flush()
    r = month_summary(s, M, TODAY)
    assert [c.name for c in r.categories] == ["Élelmiszer", "Rezsi", "Ruha"]
    assert sum(c.spent_eur_minor for c in r.categories) == r.expense_eur_minor


@pytest.mark.parametrize("bad", ["2026-1", "2026-13", "2026-11-01", "x", ""])
def test_bad_month_is_value_error(s, household, bad):
    with pytest.raises(ValueError):
        month_summary(s, bad, TODAY)
