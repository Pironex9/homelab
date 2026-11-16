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


def test_hidden_draft_is_redacted_for_other_adult(adult2, users):
    d = add(users, "anna", status="draft", merchant="SecretMerchant",
            note="SecretNote", hidden=True, amount_minor=1234)
    html = adult2.get("/drafts").text
    assert "SecretMerchant" not in html and f"/drafts/{d}" not in html
    assert "12,34" in html and "Anna" in html
    assert adult2.get(f"/drafts/{d}").status_code == 404
    assert adult2.post(f"/drafts/{d}/confirm", data=form(users)).status_code == 404
    assert status_of(users, d) == "draft"


def test_author_sees_own_hidden_draft(adult, users):
    d = add(users, "anna", status="draft", merchant="Mine", hidden=True)
    assert "Mine" in adult.get("/drafts").text
    assert adult.get(f"/drafts/{d}").status_code == 200


def test_confirm_keeps_draft_wallet(adult, users):
    from helpers import child_wallet
    d = make_draft(users)
    r = adult.post(f"/drafts/{d}/confirm", data=form(
        users, wallet_id=str(child_wallet(users))))
    assert r.status_code == 303
    hh = household(users)
    with users.state.db.session() as s:
        assert s.get(Entry, d).wallet_id == hh


def test_delete_from_draft_returns_to_drafts(adult, users):
    d = make_draft(users)
    r = adult.post(f"/entries/{d}/delete", data=dict(next="/drafts"))
    assert r.status_code == 303 and r.headers["location"] == "/drafts"
    for bad in ("//evil.example", "https://evil.example", "drafts"):
        d = make_draft(users)
        r = adult.post(f"/entries/{d}/delete", data=dict(next=bad))
        assert r.headers["location"] == "/entries"
    assert 'name="next" value="/drafts"' in adult.get(
        f"/drafts/{make_draft(users)}").text


def test_huge_amount_422(adult, users):
    d = make_draft(users)
    r = adult.post(f"/drafts/{d}/confirm", data=form(users, amount="9" * 30))
    assert r.status_code == 422


def test_other_adult_confirms_a_revealed_hidden_draft(adult2, users):
    # Hidden until a day already past: no longer a secret, so the other adult
    # may confirm it, and the form (which shows no secrecy fields to a
    # non-author) must not count as an attempt to unhide it.
    d = add(users, "anna", status="draft", merchant="Gift", hidden=True,
            reveal_on="2000-01-01")
    r = adult2.post(f"/drafts/{d}/confirm", data=form(users))
    assert r.status_code == 303
    with users.state.db.session() as s:
        e = s.get(Entry, d)
        assert e.status == "confirmed"
        assert e.hidden and e.reveal_on == "2000-01-01"


def test_draft_confirm_shows_the_rate_used(adult, users):
    from decimal import Decimal
    d = add(users, "anna", status="draft", currency="HUF",
            amount_minor=500000, manual_rate=Decimal("400"))
    html = adult.get(f"/drafts/{d}").text
    assert S["fx_line"].format(rate="400", currency="HUF", eur="12,50") in html
