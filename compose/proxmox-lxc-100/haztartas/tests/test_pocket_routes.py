from sqlalchemy import select

from app import clock
from app.models import Entry
from helpers import add, cat, child_wallet, household
from app.strings.hu import S


def rows(app, wallet):
    with app.state.db.session() as s:
        return list(s.scalars(select(Entry).where(Entry.wallet_id == wallet)))


def test_child_cannot_topup_or_set_opening(child, users):
    w = child_wallet(users)
    body = dict(wallet_id=str(w), amount="5", currency="EUR", date=clock.today())
    assert child.post("/pocket/topup", data=body).status_code == 403
    assert child.post("/pocket/opening", data=body).status_code == 403
    assert rows(users, w) == []


def test_topup_creates_pair_visible_to_child(adult, child, users):
    w = child_wallet(users)
    r = adult.post("/pocket/topup", data=dict(
        wallet_id=str(w), amount="5,50", currency="EUR", date=clock.today()))
    assert r.status_code == 303
    assert len(rows(users, household(users))) == 1
    html = child.get("/pocket").text
    assert "Zsebpénz: Cili" in html and "5,50 EUR" in html
    note = {e.note for e in rows(users, w) + rows(users, household(users))}
    assert note == {"Zsebpénz: Cili"}


def test_topup_bad_amount_422(adult, users):
    w = child_wallet(users)
    r = adult.post("/pocket/topup", data=dict(
        wallet_id=str(w), amount="abc", currency="EUR", date=clock.today()))
    assert r.status_code == 422 and S["amount_invalid"] in r.text
    assert 'value="abc"' in r.text
    assert rows(users, w) == []


def test_topup_non_child_wallet_rejected(adult, users):
    r = adult.post("/pocket/topup", data=dict(
        wallet_id=str(household(users)), amount="5", currency="EUR",
        date=clock.today()))
    assert r.status_code in (403, 404, 422)
    assert rows(users, household(users)) == []


def test_topup_missing_rate_422(adult, users):
    w = child_wallet(users)
    r = adult.post("/pocket/topup", data=dict(
        wallet_id=str(w), amount="500", currency="HUF", date=clock.today()))
    assert r.status_code == 422 and S["rate_needed"] in r.text
    assert rows(users, w) == []


def test_opening_balance(adult, child, users):
    w = child_wallet(users)
    r = adult.post("/pocket/opening", data=dict(
        wallet_id=str(w), amount="20", currency="EUR", date=clock.today()))
    assert r.status_code == 303
    (e,) = rows(users, w)
    assert e.kind == "income" and e.note == "Nyitó egyenleg"
    assert e.category_id == cat(users, "Egyéb bevétel", "income")
    assert rows(users, household(users)) == []
    assert "20,00 EUR" in child.get("/pocket").text


def test_child_pocket_shows_only_own_wallet(child, adult, users):
    other = child_wallet(users)
    add(users, "anna", wallet_id=household(users), merchant="HouseholdShop")
    add(users, "cili", wallet_id=other, merchant="Candy", amount_minor=200)
    html = child.get("/pocket").text
    assert "Candy" in html and "HouseholdShop" not in html


def test_adult_sees_each_child_wallet(adult, users):
    w = child_wallet(users)
    add(users, "cili", wallet_id=w, merchant="Candy", amount_minor=200)
    html = adult.get("/pocket").text
    assert "Cili" in html and "Candy" in html


def test_huge_topup_amount_422(adult, users):
    w = child_wallet(users)
    r = adult.post("/pocket/topup", data=dict(
        wallet_id=str(w), amount="9" * 30, currency="EUR", date=clock.today()))
    assert r.status_code == 422 and rows(users, w) == []


def test_redacted_row_shows_author_not_text(adult2, users):
    w = child_wallet(users)
    add(users, "anna", wallet_id=w, kind="income", merchant="SecretGift",
        note="SecretNote", hidden=True, amount_minor=777,
        category_id=cat(users, "Egyéb bevétel", "income"))
    html = adult2.get("/pocket").text
    assert "SecretGift" not in html and "SecretNote" not in html
    assert S["redacted_entry"] in html and "7,77 EUR" in html and "Anna" in html


def test_topup_can_be_undone_from_its_entry(adult, adult2, child, users):
    w = child_wallet(users)
    adult.post("/pocket/topup", data=dict(
        wallet_id=str(w), amount="5,50", currency="EUR", date=clock.today()))
    [half] = rows(users, w)
    assert f'href="/entries/{half.id}"' in adult.get("/pocket").text
    html = adult2.get(f"/entries/{half.id}").text   # either adult may undo it
    assert f'action="/entries/{half.id}/delete"' in html
    assert 'name="next" value="/pocket"' in html
    r = adult2.post(f"/entries/{half.id}/delete", data=dict(next="/pocket"))
    assert r.status_code == 303 and r.headers["location"] == "/pocket"
    both = rows(users, w) + rows(users, household(users))
    assert len(both) == 2 and all(e.deleted_at for e in both)


def test_child_gets_no_undo_on_a_topup(adult, child, users):
    w = child_wallet(users)
    adult.post("/pocket/topup", data=dict(
        wallet_id=str(w), amount="5,50", currency="EUR", date=clock.today()))
    [half] = rows(users, w)
    assert f'href="/entries/{half.id}"' not in child.get("/pocket").text
    html = child.get(f"/entries/{half.id}").text
    assert "/delete" not in html
