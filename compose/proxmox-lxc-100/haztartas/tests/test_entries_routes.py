from sqlalchemy import func, select

from app import clock
from app.models import Entry
from helpers import add, cat, child_wallet, form, household
from app.strings.hu import S


def count(app):
    with app.state.db.session() as s:
        return s.scalar(select(func.count()).select_from(Entry))


def test_anonymous_is_sent_to_login(client):
    assert client.get("/entries").status_code == 303
    assert client.get("/entries/new").status_code == 303


def test_new_form_defaults(adult, users):
    r = adult.get("/entries/new")
    assert r.status_code == 200
    assert clock.today() in r.text
    assert S["category_business_hint"] in r.text
    assert 'value="EUR" selected' in r.text or 'selected value="EUR"' in r.text
    assert 'name="reveal_on"' in r.text


def test_post_creates_entry_and_redirects(adult, users):
    r = adult.post("/entries", data=form(users))
    assert r.status_code == 303
    assert count(users) == 1
    assert "Tesco" in adult.get("/entries").text


def test_category_is_required(adult, users):
    r = adult.post("/entries", data=form(users, category_id=""))
    assert r.status_code == 422
    assert S["category_required"] in r.text
    assert count(users) == 0


def test_bad_amount_422_keeps_values(adult, users):
    r = adult.post("/entries", data=form(users, amount="12,345", merchant="Coop"))
    assert r.status_code == 422
    assert S["amount_invalid"] in r.text
    assert 'value="12,345"' in r.text
    assert 'value="Coop"' in r.text
    assert count(users) == 0


def test_missing_rate_asks_for_one_and_keeps_values(adult, users):
    r = adult.post("/entries", data=form(users, currency="HUF", amount="5000"))
    assert r.status_code == 422
    assert S["rate_needed"] in r.text
    assert 'name="manual_rate"' in r.text
    ok = adult.post("/entries", data=form(
        users, currency="HUF", amount="5000", manual_rate="400"))
    assert ok.status_code == 303 and count(users) == 1


def test_duplicate_prompt_then_save_anyway(adult, adult2, users):
    add(users, "bela", amount_minor=1250)
    r = adult.post("/entries", data=form(users))
    assert r.status_code == 200
    assert S["duplicate_save"] in r.text and S["duplicate_cancel"] in r.text
    assert count(users) == 1
    r2 = adult.post("/entries", data=form(users, confirm_duplicate="1"))
    assert r2.status_code == 303
    assert count(users) == 2


def test_duplicate_hint_for_secret_hides_merchant(adult, adult2, users):
    add(users, "bela", amount_minor=1250, merchant="Parfümória", hidden=True)
    r = adult.post("/entries", data=form(users))
    assert S["duplicate_secret"] in r.text
    assert "Parfümória" not in r.text


def test_child_cannot_post_household_income_403(child, users):
    r = child.post("/entries", data=form(
        users, kind="income", category_id=str(cat(users, "Fizetés", "income"))))
    assert r.status_code == 403
    assert count(users) == 0


def test_child_form_offers_household_and_own_wallet(child, users):
    own = child_wallet(users)
    r = child.get("/entries/new")
    assert f'value="{household(users)}"' in r.text
    assert f'value="{own}"' in r.text


def test_child_can_spend_from_own_wallet(child, users):
    own = child_wallet(users)
    r = child.post("/entries", data=form(users, wallet_id=str(own)))
    assert r.status_code == 303 and count(users) == 1


def test_redacted_row_has_no_merchant(adult, adult2, users):
    add(users, "bela", merchant="Parfümória", note="titok", hidden=True)
    html = adult.get("/entries").text
    assert "Parfümória" not in html and "titok" not in html
    assert S["redacted_entry"] in html
    assert "10,00 EUR" in html


def test_redacted_row_has_no_detail_link(adult, adult2, users):
    eid = add(users, "bela", hidden=True)
    assert f"/entries/{eid}" not in adult.get("/entries").text


def test_redacted_entry_detail_404_for_others(adult, adult2, users):
    eid = add(users, "bela", merchant="Parfümória", hidden=True)
    assert adult.get(f"/entries/{eid}").status_code == 404
    assert adult2.get(f"/entries/{eid}").status_code == 200


def test_child_does_not_see_household_entries(child, adult, users):
    add(users, "anna", merchant="Lidl")
    assert "Lidl" not in child.get("/entries").text


def test_search_finds_own_hidden(adult, adult2, users):
    add(users, "anna", merchant="Parfümória", hidden=True)
    assert "Parfümória" in adult.get("/entries?q=parfumoria").text


def test_search_does_not_match_others_secret(adult, adult2, users):
    add(users, "bela", merchant="Parfümória", hidden=True)
    html = adult.get("/entries?q=parfumoria").text
    assert S["redacted_entry"] not in html


def test_filter_by_category_and_month(adult, users):
    add(users, "anna", merchant="Lidl")
    add(users, "anna", merchant="Shell", category_id=cat(users, "Autó"))
    only = adult.get(f"/entries?category={cat(users, 'Autó')}").text
    assert "Shell" in only and "Lidl" not in only
    assert "Lidl" not in adult.get("/entries?month=2020-01").text


def test_edit_updates_entry(adult, users):
    eid = add(users, "anna")
    r = adult.post(f"/entries/{eid}", data=form(users, merchant="Billa"))
    assert r.status_code == 303
    assert "Billa" in adult.get(f"/entries/{eid}").text


def test_edit_bad_amount_422(adult, users):
    eid = add(users, "anna")
    r = adult.post(f"/entries/{eid}", data=form(users, amount="x"))
    assert r.status_code == 422


def test_delete_hides_entry(adult, users):
    eid = add(users, "anna")
    assert adult.post(f"/entries/{eid}/delete").status_code == 303
    assert adult.get(f"/entries/{eid}").status_code == 404
    assert "Lidl" not in adult.get("/entries").text


def test_only_author_can_reveal(adult, adult2, users):
    eid = add(users, "anna", hidden=True)
    assert adult2.post(f"/entries/{eid}/reveal").status_code == 403
    assert adult.post(f"/entries/{eid}/reveal").status_code == 303
    assert "Lidl" in adult2.get("/entries").text


def test_child_cannot_delete_adult_entry(child, adult, users):
    eid = add(users, "anna")
    assert child.post(f"/entries/{eid}/delete").status_code in (403, 404)
