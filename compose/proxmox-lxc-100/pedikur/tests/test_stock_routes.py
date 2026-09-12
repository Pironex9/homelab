"""The stock screen through the real app.

The service tests cover the rules; these cover what a mistyped form does,
which is the part that turns into a 500 when nobody checks.
"""
from app.services import products, stock


def _product(client, name="Lakk", unit="flakon", **kw):
    with client.app.state.db.session() as s:
        return products.create(s, name, unit, created_by="1", **kw).id


def test_the_stock_screen_needs_a_login(client):
    assert client.get("/stock").status_code == 303


def test_a_new_product_can_be_created_with_its_opening_stock(logged_in):
    r = logged_in.post("/stock/products", data={
        "name": "Lakk", "unit": "flakon", "min_stock": "2",
        "opening_qty": "3", "opening_cost_eur": "12,50"})
    assert r.status_code == 303
    with logged_in.app.state.db.session() as s:
        level = stock.levels(s)[0]
        assert level.product.name == "Lakk"
        assert level.qty == 3.0
        # The opening cost is what every later consumption is charged at
        assert stock.last_cost_cents(s, level.product.id) == 1250


def test_a_new_product_without_an_opening_quantity_writes_no_movement(logged_in):
    logged_in.post("/stock/products",
                   data={"name": "Lakk", "unit": "flakon", "min_stock": "0",
                         "opening_qty": "", "opening_cost_eur": ""})
    with logged_in.app.state.db.session() as s:
        assert stock.levels(s)[0].qty == 0.0


def test_a_mistyped_opening_price_does_not_create_a_half_product(logged_in):
    """Either the product and its opening movement both exist, or neither
    does. A product created with a silently dropped opening quantity is worse
    than a refused form: nothing says the stock is wrong."""
    r = logged_in.post("/stock/products", data={
        "name": "Lakk", "unit": "flakon", "min_stock": "0",
        "opening_qty": "3", "opening_cost_eur": "tizenketto"})
    assert r.status_code == 303
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert products.list_all(s) == []


def test_a_negative_minimum_says_so_rather_than_blaming_the_name(logged_in):
    r = logged_in.post("/stock/products", data={
        "name": "Lakk", "unit": "flakon", "min_stock": "-2",
        "opening_qty": "", "opening_cost_eur": ""})
    assert "error=stock_qty_invalid" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert products.list_all(s) == []


def test_a_waste_movement_takes_stock_off_the_shelf(logged_in):
    pid = _product(logged_in)
    logged_in.post(f"/stock/{pid}/movement",
                   data={"qty": "3", "reason": "opening", "cost_eur": "12,00"})
    logged_in.post(f"/stock/{pid}/movement",
                   data={"qty": "1", "reason": "waste", "cost_eur": ""})
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, pid) == 2.0


def test_a_correction_may_be_negative(logged_in):
    pid = _product(logged_in)
    logged_in.post(f"/stock/{pid}/movement",
                   data={"qty": "-2", "reason": "correction", "cost_eur": ""})
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, pid) == -2.0


def test_consumption_cannot_be_typed_by_hand(logged_in):
    """It is posted by the close path. Allowing it here would let one bottle
    be counted twice, once by her and once by the app."""
    pid = _product(logged_in)
    r = logged_in.post(f"/stock/{pid}/movement",
                       data={"qty": "1", "reason": "consumption",
                             "cost_eur": ""})
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, pid) == 0.0


def test_archiving_a_product_takes_it_off_the_screen(logged_in):
    pid = _product(logged_in)
    logged_in.post(f"/stock/{pid}/archive")
    assert "Lakk" not in logged_in.get("/stock").text
    assert "Lakk" in logged_in.get("/stock?archived=true").text
    logged_in.post(f"/stock/{pid}/unarchive")
    assert "Lakk" in logged_in.get("/stock").text


def test_a_stale_product_id_reloads_the_screen_rather_than_crashing(logged_in):
    r = logged_in.post("/stock/9999/archive")
    assert r.status_code == 303
    assert logged_in.get("/stock").status_code == 200


def test_a_movement_on_a_stale_product_id_does_not_500(logged_in):
    r = logged_in.post("/stock/9999/movement",
                       data={"qty": "1", "reason": "correction",
                             "cost_eur": ""})
    assert r.status_code == 303
