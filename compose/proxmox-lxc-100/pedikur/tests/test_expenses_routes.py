"""The expense screen through the real app.

The service tests cover the rules; these cover what a mistyped form does,
which is the part that turns into a 500 when nobody checks.
"""
from app.services import expenses, products, stock


def test_the_expense_screen_needs_a_login(client):
    assert client.get("/expenses").status_code == 303


def test_an_expense_is_recorded_from_the_form(logged_in):
    r = logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "rezsi", "vendor": "Áram",
        "amount_eur": "45,00", "note": ""})
    assert r.status_code == 303
    with logged_in.app.state.db.session() as s:
        assert expenses.recent(s)[0].amount_cents == 4500


def test_a_line_on_the_form_puts_the_goods_into_stock(logged_in):
    with logged_in.app.state.db.session() as s:
        lakk_id = products.create(s, "Lakk", "flakon", created_by="1").id
    logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "anyag", "vendor": "Nagyker",
        "amount_eur": "24,00", "note": "",
        "line_product_id": str(lakk_id), "line_qty": "2",
        "line_cost_eur": "12,00"})
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, lakk_id) == 2.0


def test_a_mistyped_amount_writes_nothing_at_all(logged_in):
    r = logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "anyag", "vendor": "",
        "amount_eur": "negyven", "note": ""})
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert expenses.recent(s) == []


def test_a_mistyped_line_leaves_no_expense_behind(logged_in):
    with logged_in.app.state.db.session() as s:
        lakk_id = products.create(s, "Lakk", "flakon", created_by="1").id
    r = logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "anyag", "vendor": "",
        "amount_eur": "24,00", "note": "",
        "line_product_id": str(lakk_id), "line_qty": "kettő",
        "line_cost_eur": "12,00"})
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert expenses.recent(s) == []
        assert stock.quantity(s, lakk_id) == 0.0


def test_a_bad_date_says_so_rather_than_500ing(logged_in):
    r = logged_in.post("/expenses", data={
        "date": "tegnap", "category": "anyag", "vendor": "",
        "amount_eur": "24,00", "note": ""})
    assert "error=expense_date_invalid" in r.headers["location"]


def test_an_invented_category_says_so(logged_in):
    r = logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "kávé", "vendor": "",
        "amount_eur": "24,00", "note": ""})
    assert "error=expense_category_invalid" in r.headers["location"]


def test_a_recorded_expense_is_listed_with_its_category(logged_in):
    logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "berleti_dij", "vendor": "Tulaj",
        "amount_eur": "300,00", "note": "szeptember"})
    page = logged_in.get("/expenses").text
    assert "Tulaj" in page
    assert "Bérleti díj" in page
    assert "300,00 EUR" in page
    assert "szeptember" in page


def test_deleting_from_the_screen_reverses_the_stock(logged_in):
    with logged_in.app.state.db.session() as s:
        lakk_id = products.create(s, "Lakk", "flakon", created_by="1").id
    logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "anyag", "vendor": "",
        "amount_eur": "24,00", "note": "",
        "line_product_id": str(lakk_id), "line_qty": "2",
        "line_cost_eur": "12,00"})
    with logged_in.app.state.db.session() as s:
        e_id = expenses.recent(s)[0].id
    logged_in.post(f"/expenses/{e_id}/delete")
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, lakk_id) == 0.0


def test_a_stale_expense_id_does_not_500(logged_in):
    assert logged_in.post("/expenses/9999/delete").status_code == 303
