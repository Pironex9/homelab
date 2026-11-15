from sqlalchemy import select

from app.models import Category, Recurring
from helpers import add, cat, user
from app.strings.hu import S


def cat_row(app, cid):
    with app.state.db.session() as s:
        return s.get(Category, cid)


def test_child_settings_403(child, users):
    cid = cat(users, "Élelmiszer")
    assert child.get("/settings").status_code == 403
    assert child.post(f"/settings/categories/{cid}", data=dict(
        name="X", limit="", sort="1")).status_code == 403
    assert child.post("/settings/categories", data=dict(
        name="X", kind="expense", sort="1")).status_code == 403
    assert child.post(f"/settings/categories/{cid}/archive").status_code == 403
    assert cat_row(users, cid).name == "Élelmiszer"


def test_page_lists_categories_and_recurring(adult, users):
    html = adult.get("/settings").text
    assert "Élelmiszer" in html and "Egyéb bevétel" in html


def test_rename_and_sort(adult, users):
    cid = cat(users, "Ruha")
    r = adult.post(f"/settings/categories/{cid}", data=dict(
        name="Ruházat", limit="", sort="42"))
    assert r.status_code == 303
    c = cat_row(users, cid)
    assert (c.name, c.sort, c.monthly_limit_eur_minor) == ("Ruházat", 42, None)


def test_set_limit_shows_on_home(adult, users):
    cid = cat(users, "Élelmiszer")
    add(users, "anna", amount_minor=2000)
    assert "tile__limit" not in adult.get("/").text
    r = adult.post(f"/settings/categories/{cid}", data=dict(
        name="Élelmiszer", limit="250,50", sort="1"))
    assert r.status_code == 303
    assert cat_row(users, cid).monthly_limit_eur_minor == 25050
    assert "tile__limit" in adult.get("/").text
    # empty clears it
    adult.post(f"/settings/categories/{cid}", data=dict(
        name="Élelmiszer", limit="", sort="1"))
    assert cat_row(users, cid).monthly_limit_eur_minor is None


def test_bad_limit_422_keeps_values(adult, users):
    cid = cat(users, "Ruha")
    r = adult.post(f"/settings/categories/{cid}", data=dict(
        name="Typed name", limit="12,345", sort="3"))
    assert r.status_code == 422
    assert S["amount_invalid"] in r.text
    assert 'value="Typed name"' in r.text and 'value="12,345"' in r.text
    assert cat_row(users, cid).name == "Ruha"


def test_empty_name_and_duplicate_rejected(adult, users):
    cid = cat(users, "Ruha")
    assert adult.post(f"/settings/categories/{cid}", data=dict(
        name=" ", limit="", sort="1")).status_code == 422
    assert adult.post(f"/settings/categories/{cid}", data=dict(
        name="Autó", limit="", sort="1")).status_code == 422
    assert adult.post("/settings/categories", data=dict(
        name="autó", kind="expense", sort="1")).status_code == 422


def test_pocket_categories_cannot_be_renamed(adult, users):
    cid = cat(users, "Zsebpénz")
    r = adult.post(f"/settings/categories/{cid}", data=dict(
        name="Other", limit="", sort="1"))
    assert r.status_code == 422 and cat_row(users, cid).name == "Zsebpénz"


def test_add_category(adult, users):
    r = adult.post("/settings/categories", data=dict(
        name="Kert", kind="expense", sort="30"))
    assert r.status_code == 303
    with users.state.db.session() as s:
        c = s.scalars(select(Category).where(Category.name == "Kert")).one()
        assert (c.kind, c.sort, c.archived_at) == ("expense", 30, None)
    assert adult.post("/settings/categories", data=dict(
        name="Bad", kind="nope", sort="1")).status_code == 422


def test_archived_category_not_in_form_but_history_keeps_name(adult, users):
    cid = cat(users, "Ruha")
    add(users, "anna", category_id=cid, merchant="Zara")
    assert adult.post(f"/settings/categories/{cid}/archive").status_code == 303
    assert cat_row(users, cid).archived_at is not None
    assert "Ruha" not in adult.get("/entries/new").text
    assert "Ruha" in adult.get("/entries").text
    # unarchive
    adult.post(f"/settings/categories/{cid}/archive")
    assert cat_row(users, cid).archived_at is None
    assert "Ruha" in adult.get("/entries/new").text


def rec_form(users, **kw):
    base = dict(name="Netflix", kind="expense",
                category_id=str(cat(users, "Előfizetések")), amount="9,99",
                currency="EUR", day="15", owner_user_id="")
    base.update(kw)
    return base


def only_recurring(app):
    with app.state.db.session() as s:
        return s.scalars(select(Recurring)).one()


def test_add_edit_archive_recurring(adult, users):
    assert adult.post("/settings/recurring", data=rec_form(users)).status_code == 303
    r = only_recurring(users)
    assert (r.name, r.amount_minor, r.day_of_month, r.owner_user_id) == (
        "Netflix", 999, 15, None)
    anna = user(users, "anna").id
    assert adult.post(f"/settings/recurring/{r.id}", data=rec_form(
        users, name="Spotify", amount="5", day="3",
        owner_user_id=str(anna))).status_code == 303
    r = only_recurring(users)
    assert (r.name, r.amount_minor, r.day_of_month, r.owner_user_id) == (
        "Spotify", 500, 3, anna)
    assert "Spotify" in adult.get("/settings").text
    assert adult.post(f"/settings/recurring/{r.id}/archive").status_code == 303
    assert only_recurring(users).archived_at is not None
    assert "Spotify" not in adult.get("/settings").text


def test_recurring_validation_422(adult, users):
    for bad in (dict(day="0"), dict(day="32"), dict(day="x"),
                dict(amount="zz"), dict(name=""), dict(currency="XXX"),
                dict(kind="income"),            # category is an expense one
                dict(owner_user_id=str(user(users, "cili").id)),
                dict(category_id="99999")):
        r = adult.post("/settings/recurring", data=rec_form(users, **bad))
        assert r.status_code == 422, bad
    with users.state.db.session() as s:
        assert s.scalars(select(Recurring)).first() is None
    r = adult.post("/settings/recurring", data=rec_form(users, name="Keep me", day="40"))
    assert 'value="Keep me"' in r.text


def test_child_cannot_touch_recurring(child, users):
    assert child.post("/settings/recurring", data=rec_form(users)).status_code == 403


def test_cannot_archive_category_used_by_active_recurring(adult, users):
    adult.post("/settings/recurring", data=rec_form(users))
    cid = cat(users, "Előfizetések")
    r = adult.post(f"/settings/categories/{cid}/archive")
    assert r.status_code == 422 and S["e_archive_in_use"] in r.text
    assert cat_row(users, cid).archived_at is None
    rid = only_recurring(users).id
    adult.post(f"/settings/recurring/{rid}/archive")
    assert adult.post(f"/settings/categories/{cid}/archive").status_code == 303


def test_cannot_archive_locked_categories(adult, users):
    for name, kind in (("Zsebpénz", "expense"), ("Egyéb bevétel", "income")):
        cid = cat(users, name, kind)
        r = adult.post(f"/settings/categories/{cid}/archive")
        assert r.status_code == 422 and S["e_archive_locked"] in r.text
        assert cat_row(users, cid).archived_at is None
