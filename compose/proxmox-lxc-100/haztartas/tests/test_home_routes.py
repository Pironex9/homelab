from app import clock
from app.strings.hu import S, MONTHS_IN
from helpers import add, cat, child_wallet, household
from app.models import Recurring
from sqlalchemy import select


def month():
    return clock.today()[:7]


def test_anonymous_is_sent_to_login(client):
    assert client.get("/").status_code == 303


def test_adult_home_shows_balance_tiles_and_authors(adult, users):
    add(users, "anna", amount_minor=30000)
    add(users, "bela", amount_minor=10000, category_id=cat(users, "Autó"))
    add(users, "anna", kind="income", amount_minor=100000, merchant=None,
        category_id=cat(users, "Fizetés", "income"))
    html = adult.get("/").text
    assert "600,00 EUR" in html           # 1000 - 300 - 100
    assert "Élelmiszer" in html and "Autó" in html
    assert "Ki mennyit költött" in html
    assert f"/entries?month={month()}&amp;category={cat(users, 'Élelmiszer')}" in html


def test_tile_hue_note_and_size(adult, adult2, users):
    food = cat(users, "Élelmiszer")
    add(users, "anna", amount_minor=90000, category_id=food)
    add(users, "bela", amount_minor=1000, category_id=food, hidden=True)
    add(users, "anna", amount_minor=1000, category_id=cat(users, "Autó"))
    html = adult.get("/").text
    assert f"tile c{food % 8} tile--big" in html
    assert "1 rejtett tétel" in html


def test_small_categories_fold_into_other(adult, users):
    add(users, "anna", amount_minor=100000)
    for name in ("Autó", "Ruha", "Ajándék"):
        add(users, "anna", amount_minor=100, category_id=cat(users, name))
    html = adult.get("/").text
    assert "Egyéb · 3 kategória" in html and "c-other" in html


def test_over_limit_tile(adult, users):
    from app.models import Category
    food = cat(users, "Élelmiszer")
    with users.state.db.session() as s:
        s.get(Category, food).monthly_limit_eur_minor = 5000
    add(users, "anna", amount_minor=8000)
    html = adult.get("/").text
    assert "tile--over" in html and "--used:100%" in html


def test_month_param_and_navigation(adult, users):
    html = adult.get("/").text
    assert 'aria-label="%s"' % S["month_prev"] in html
    assert 'aria-label="%s"' % S["month_next"] not in html     # current month
    past = adult.get("/?month=2020-01").text
    assert "2020" in past and MONTHS_IN[0] in past
    assert 'aria-label="%s"' % S["month_next"] in past
    assert adult.get("/?month=garbage").status_code == 200


def test_expected_income_only_for_current_month(adult, users):
    with users.state.db.session() as s:
        s.add(Recurring(name="Fizetés", kind="income",
                        category_id=cat(users, "Fizetés", "income"),
                        amount_minor=100000, currency="EUR", day_of_month=10))
    assert S["expected_prefix"] in adult.get("/").text
    assert S["expected_prefix"] not in adult.get("/?month=2020-01").text


def test_child_home_has_no_household_balance(child, adult, users):
    add(users, "anna", kind="income", amount_minor=987654, merchant=None,
        category_id=cat(users, "Fizetés", "income"))
    own = child_wallet(users)
    add(users, "cili", wallet_id=own, amount_minor=500, merchant="Fagyi",
        category_id=cat(users, "Szórakozás"))
    r = child.get("/")
    assert r.status_code == 200
    assert "ennyi maradt" not in r.text
    assert "9 876,54" not in r.text and "9876" not in r.text
    assert S["map_title_adult"] not in r.text
    assert S["by_author"] not in r.text
    assert "Fagyi" in r.text and "Szórakozás" in r.text


def test_child_balance_and_entries_list(child, adult, users):
    own = child_wallet(users)
    from app.services.entries import top_up
    with users.state.db.session() as s:
        from helpers import user
        top_up(s, user(users, "anna"), own, 2000, "EUR", clock.today())
    add(users, "cili", wallet_id=own, amount_minor=500, merchant="Fagyi",
        category_id=cat(users, "Szórakozás"))
    html = child.get("/").text
    assert "15,00 EUR" in html
    assert "Fagyi" in html


def test_child_sees_at_most_20_entries(child, users):
    own = child_wallet(users)
    for i in range(25):
        add(users, "cili", wallet_id=own, amount_minor=100, merchant=f"Bolt{i:02d}",
            category_id=cat(users, "Szórakozás"))
    html = child.get("/").text
    assert html.count('class="what"') == 20


def test_child_home_lists_entries_across_both_wallets(child, adult, users):
    own = child_wallet(users)
    add(users, "cili", merchant="KozosBolt", category_id=cat(users, "Szórakozás"))
    add(users, "cili", wallet_id=own, merchant="SajatBolt",
        category_id=cat(users, "Szórakozás"))
    add(users, "anna", merchant="SzuloBolt")
    html = child.get("/").text
    assert "KozosBolt" in html and "SajatBolt" in html
    assert "SzuloBolt" not in html


def test_other_tile_is_not_a_sliver(adult, users):
    add(users, "anna", amount_minor=100000)
    for name in ("Autó", "Ruha"):
        add(users, "anna", amount_minor=100, category_id=cat(users, name))
    import re
    html = adult.get("/").text
    m = re.search(r'c-other[^>]*--w:([\d.]+);--h:([\d.]+)', html)
    assert m and float(m[1]) * float(m[2]) >= 0.06 * 10000 - 1
