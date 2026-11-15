from sqlalchemy import select

from app import clock
from app.models import Entry
from app.services import recurring
from helpers import add, cat, form, household
from app.strings.hu import S


def make_draft(app, **kw):
    return add(app, "anna", status="draft", merchant="Rent", **kw)


def status_of(app, entry_id):
    with app.state.db.session() as s:
        return s.get(Entry, entry_id).status


def test_child_drafts_403(child, users):
    d = make_draft(users)
    assert child.get("/drafts").status_code == 403
    assert child.get(f"/drafts/{d}").status_code == 403
    assert child.post(f"/drafts/{d}/confirm", data=form(users)).status_code == 403
    assert status_of(users, d) == "draft"


def test_list_shows_only_household_drafts(adult, users):
    make_draft(users, amount_minor=45000)
    add(users, "anna", merchant="Confirmed Shop")
    html = adult.get("/drafts").text
    assert "Rent" in html and "Confirmed Shop" not in html


def test_confirm_with_corrected_amount(adult, users):
    d = make_draft(users, amount_minor=45000)
    page = adult.get(f"/drafts/{d}")
    assert page.status_code == 200 and 'value="450,00"' in page.text
    r = adult.post(f"/drafts/{d}/confirm", data=form(
        users, amount="432,10", merchant="Rent"))
    assert r.status_code == 303
    with users.state.db.session() as s:
        e = s.get(Entry, d)
        assert e.status == "confirmed" and e.amount_minor == 43210


def test_confirm_bad_amount_422_keeps_values(adult, users):
    d = make_draft(users)
    r = adult.post(f"/drafts/{d}/confirm", data=form(
        users, amount="x", merchant="Typed"))
    assert r.status_code == 422
    assert S["amount_invalid"] in r.text and 'value="Typed"' in r.text
    assert status_of(users, d) == "draft"


def test_confirmed_or_missing_is_404(adult, users):
    c = add(users, "anna")
    assert adult.get(f"/drafts/{c}").status_code == 404
    assert adult.post(f"/drafts/{c}/confirm", data=form(users)).status_code == 404
    assert adult.get("/drafts/99999").status_code == 404


def test_home_counts_drafts(adult, users):
    make_draft(users)
    make_draft(users, date="2026-01-01")
    html = adult.get("/").text
    assert '<span class="count">2</span>' in html


def test_recurring_drafts_listed(adult, users):
    from app.models import Recurring
    with users.state.db.session() as s:
        s.add(Recurring(name="Salary", kind="income",
                        category_id=cat(users, "Fizetés", "income"),
                        amount_minor=100000, currency="EUR", day_of_month=1))
        recurring.create_due_drafts(s, clock.today())
    assert "Salary" in adult.get("/drafts").text
