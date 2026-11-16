import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import fx, migrate
from app.db import Database
from app.models import Category, Entry, Recurring, User, Wallet
from app.services import recurring
from app.services.entries import EntryInput, NotAllowed


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
def child(s):
    return _user(s, "cili", "child")


@pytest.fixture
def household(s):
    return s.scalars(select(Wallet).where(Wallet.owner_user_id.is_(None))).one()


def _cat(s, kind):
    return s.scalars(select(Category).where(Category.kind == kind)).first().id


def _item(s, day=10, amount=200000, currency="EUR", kind="income", owner=None,
          archived=None, name="Salary"):
    r = Recurring(name=name, kind=kind, category_id=_cat(s, kind),
                  amount_minor=amount, currency=currency, day_of_month=day,
                  owner_user_id=owner.id if owner else None,
                  archived_at=archived)
    s.add(r)
    s.flush()
    return r


def _entries(s):
    return list(s.scalars(select(Entry).order_by(Entry.id)))


def test_draft_created_once(s, adult, household):
    r = _item(s, owner=adult)
    assert recurring.create_due_drafts(s, "2026-11-12") == 1
    assert recurring.create_due_drafts(s, "2026-11-12") == 0
    [e] = _entries(s)
    assert (e.status, e.source, e.date, e.recurring_id, e.recurring_month) == (
        "draft", "recurring", "2026-11-10", r.id, "2026-11")
    assert (e.wallet_id, e.created_by, e.kind) == (
        household.id, adult.id, "income")
    assert (e.amount_minor, e.eur_minor, e.fx_rate) == (200000, 200000, "1")


def test_not_before_its_day(s, adult):
    _item(s, day=15)
    assert recurring.create_due_drafts(s, "2026-11-14") == 0
    assert _entries(s) == []
    assert recurring.create_due_drafts(s, "2026-11-15") == 1


def test_day_clamped_and_new_month_new_draft(s, adult):
    _item(s, day=31)
    assert recurring.create_due_drafts(s, "2026-02-27") == 0
    assert recurring.create_due_drafts(s, "2026-02-28") == 1
    assert recurring.create_due_drafts(s, "2026-03-31") == 1
    assert [e.date for e in _entries(s)] == ["2026-02-28", "2026-03-31"]


def test_author_falls_back_to_first_adult(s, adult):
    _user(s, "bela", "adult")
    _item(s)
    recurring.create_due_drafts(s, "2026-11-12")
    assert _entries(s)[0].created_by == adult.id


def test_expense_gets_draft_archived_does_not(s, adult):
    _item(s, kind="expense", name="Rent")
    _item(s, archived="2026-10-01T00:00:00Z", name="Old")
    assert recurring.create_due_drafts(s, "2026-11-12") == 1
    assert _entries(s)[0].kind == "expense"


def test_foreign_currency_uses_rate_of_the_day(s, adult):
    _item(s, amount=4000000, currency="HUF")
    recurring.create_due_drafts(s, "2026-11-12")
    assert _entries(s)[0].eur_minor == 10000   # 40000.00 HUF at 400 = 100.00 EUR


def test_needs_rate_is_skipped_and_others_continue(s, adult, caplog):
    _item(s, currency="CZK", name="Czech")
    _item(s, name="Salary")
    assert recurring.create_due_drafts(s, "2026-11-12") == 1
    assert [e.currency for e in _entries(s)] == ["EUR"]
    assert "Czech" in caplog.text
    fx.store(s, [("2026-11-10", "CZK", Decimal("25"))])
    assert recurring.create_due_drafts(s, "2026-11-12") == 1


def test_race_on_unique_counts_as_already_created(s, adult, monkeypatch):
    r = _item(s)
    # The pre-check says "none yet", but another worker got there first.
    recurring.create_due_drafts(s, "2026-11-12")
    monkeypatch.setattr(recurring, "_exists", lambda *a: False)
    assert recurring.create_due_drafts(s, "2026-11-12") == 0
    assert len(_entries(s)) == 1


def _draft(s, adult):
    _item(s, owner=adult)
    recurring.create_due_drafts(s, "2026-11-12")
    return _entries(s)[0]


def test_child_cannot_confirm(s, adult, child):
    d = _draft(s, adult)
    with pytest.raises(NotAllowed):
        recurring.confirm_draft(s, child, d.id, None)
    assert d.status == "draft"


def test_confirm_as_is_keeps_author(s, adult):
    other = _user(s, "bela", "adult")
    d = _draft(s, adult)
    e = recurring.confirm_draft(s, other, d.id, None)
    assert (e.status, e.created_by, e.amount_minor) == (
        "confirmed", adult.id, 200000)


def test_confirm_with_corrected_amount(s, adult, household):
    d = _draft(s, adult)
    data = EntryInput(
        wallet_id=household.id, kind="income", date="2026-11-12",
        amount_minor=5000000, currency="HUF", category_id=d.category_id,
        merchant=None, note=None, payment="other", hidden=False,
        reveal_on=None)
    e = recurring.confirm_draft(s, adult, d.id, data)
    assert (e.status, e.amount_minor, e.currency, e.eur_minor, e.fx_rate) == (
        "confirmed", 5000000, "HUF", 10000, "500")
    assert e.source == "recurring" and e.recurring_month == "2026-11"


def test_confirm_twice_or_missing_refused(s, adult):
    d = _draft(s, adult)
    recurring.confirm_draft(s, adult, d.id, None)
    with pytest.raises(ValueError):
        recurring.confirm_draft(s, adult, d.id, None)
    with pytest.raises(NotAllowed):
        recurring.confirm_draft(s, adult, 9999, None)


class _Stop(Exception):
    pass


def test_daily_task_runs_survives_errors_and_sleeps_injected(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    db = Database(db_path)
    with db.session() as s:
        _user(s, "anna", "adult")
        _item(s)
    calls = []

    async def sleep(seconds):
        calls.append(seconds)
        if len(calls) == 3:
            raise _Stop
    days = iter(["bad", "2026-11-12", "2026-11-12"])

    def clock():
        d = next(days)
        if d == "bad":
            raise RuntimeError("boom")
        return d

    with pytest.raises(_Stop):
        asyncio.run(recurring.daily_task(db, interval=7, today=clock,
                                         sleep=sleep))
    assert calls == [7, 7, 7]
    with db.session() as s:
        assert len(_entries(s)) == 1
