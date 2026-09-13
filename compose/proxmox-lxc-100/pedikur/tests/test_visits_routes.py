"""The booking form through the real app.

Every one of these is a shape of bad input that would otherwise be a 500 or a
raw FastAPI 422 JSON body instead of the form saying what went wrong.
"""
import pytest


@pytest.fixture
def booked(logged_in):
    logged_in.post("/clients", data={"name": "Kovács Anna", "phone": ""})
    logged_in.post("/settings/treatments",
                   data={"name": "Pedikűr", "duration_min": "45",
                         "price_eur": "25,00"})
    return logged_in


def test_the_form_needs_a_session(client):
    assert client.get("/visits/new").status_code == 303


def test_the_form_lists_clients_and_active_treatments(booked):
    page = booked.get("/visits/new?start=2026-09-10T10:00").text
    assert "Kovács Anna" in page
    assert "Pedikűr" in page
    assert "25,00 EUR" in page
    assert 'value="2026-09-10T10:00"' in page


def test_booking_redirects_to_that_day_in_the_calendar(booked):
    r = booked.post("/visits/new", data={
        "client_id": "1", "start": "2026-09-10T10:00", "end": "",
        "treatment_ids": ["1"]})
    assert r.status_code == 303
    assert r.headers["location"] == "/calendar?day=2026-09-10"

    from app.models import Visit
    with booked.app.state.db.session() as s:
        visit = s.get(Visit, 1)
        assert visit.starts_at == "2026-09-10T08:00:00Z"   # CEST, UTC+2
        assert visit.ends_at == "2026-09-10T08:45:00Z"


def test_an_unticked_form_says_so_instead_of_returning_422_json(booked):
    r = booked.post("/visits/new", data={
        "client_id": "1", "start": "2026-09-10T10:00", "end": ""})
    assert r.status_code == 400
    assert "Válassz legalább egy kezelést" in r.text
    assert "<form" in r.text          # the form comes back, not a JSON body


def test_a_taken_slot_answers_409_with_the_form(booked):
    data = {"client_id": "1", "start": "2026-09-10T10:00", "end": "",
            "treatment_ids": ["1"]}
    assert booked.post("/visits/new", data=data).status_code == 303
    r = booked.post("/visits/new", data=data)
    assert r.status_code == 409
    assert "Ez az idősáv már foglalt" in r.text


def test_a_malformed_time_says_so(booked):
    r = booked.post("/visits/new", data={
        "client_id": "1", "start": "tegnap", "end": "",
        "treatment_ids": ["1"]})
    assert r.status_code == 400
    assert "nem értelmezhető" in r.text


def test_a_client_that_is_gone_says_so(booked):
    r = booked.post("/visits/new", data={
        "client_id": "999", "start": "2026-09-10T10:00", "end": "",
        "treatment_ids": ["1"]})
    assert r.status_code == 400
    assert "Ez a kliens már nem foglalható" in r.text

    from app.models import Visit
    with booked.app.state.db.session() as s:
        assert s.query(Visit).count() == 0


def test_a_manual_end_widens_the_window(booked):
    booked.post("/visits/new", data={
        "client_id": "1", "start": "2026-09-10T10:00",
        "end": "2026-09-10T12:00", "treatment_ids": ["1"]})
    from app.models import Visit
    with booked.app.state.db.session() as s:
        assert s.get(Visit, 1).ends_at == "2026-09-10T10:00:00Z"   # 12:00 CEST


def test_the_client_select_starts_on_nothing(booked):
    """Defaulting to the first name in the list means one careless save books
    the wrong person, which is the one mistake this screen must not make."""
    page = booked.get("/visits/new?start=2026-09-10T10:00").text
    assert "Válassz klienst" in page
    assert 'value="" selected disabled' in page
    # and it does preselect when the grid handed it one
    page = booked.get("/visits/new?start=2026-09-10T10:00&client_id=1").text
    assert 'value="1" selected' in page


@pytest.fixture
def to_close(booked):
    booked.post("/visits/new", data={
        "client_id": "1", "start": "2026-09-10T10:00", "end": "",
        "treatment_ids": ["1"]})
    return booked


def test_the_closing_screen_puts_done_before_everything_optional(to_close):
    page = to_close.get("/visits/1/close").text
    assert page.index("primary-big") < page.index("more_options"
                                                  if "more_options" in page
                                                  else "Továbbiak")
    assert page.index("primary-big") < page.index("Kezelés hozzáadása")
    assert page.index("primary-big") < page.index("Nem jött el")


def test_closing_marks_it_done_and_stamps_the_price(to_close):
    r = to_close.post("/visits/1/close", data={"findings": "", "note": ""})
    assert r.status_code == 303
    from app.models import Visit
    with to_close.app.state.db.session() as s:
        visit = s.get(Visit, 1)
        assert visit.status == "done"
        assert visit.items[0].unit_price_cents == 2500


def test_a_double_tap_on_done_does_not_post_the_line_twice(to_close):
    for _ in range(2):
        to_close.post("/visits/1/close", data={"findings": "", "note": ""})
    from app.models import VisitItem
    with to_close.app.state.db.session() as s:
        assert s.query(VisitItem).filter_by(visit_id=1).count() == 1


def test_a_price_override_is_taken_from_the_form(to_close):
    item_id = 1
    to_close.post("/visits/1/close",
                  data={"findings": "", "note": "", f"price_{item_id}": "20,00"})
    from app.models import VisitItem
    with to_close.app.state.db.session() as s:
        assert s.get(VisitItem, item_id).unit_price_cents == 2000


def test_a_mistyped_override_says_so_and_closes_nothing(to_close):
    r = to_close.post("/visits/1/close",
                      data={"findings": "", "note": "", "price_1": "húsz"})
    assert r.headers["location"].endswith("error=treatment_price_invalid")
    from app.models import Visit
    with to_close.app.state.db.session() as s:
        assert s.get(Visit, 1).status == "planned"


def test_adding_a_treatment_returns_to_the_same_screen(to_close):
    to_close.post("/settings/treatments",
                  data={"name": "Géllakk", "duration_min": "30",
                        "price_eur": "18,00"})
    r = to_close.post("/visits/1/treatments", data={"treatment_id": "2"})
    assert r.headers["location"] == "/visits/1/close"
    assert "Géllakk" in to_close.get("/visits/1/close").text


def test_marking_a_no_show_does_not_500(to_close):
    r = to_close.post("/visits/1/status", data={"value": "no_show"})
    assert r.status_code == 303
    from app.models import Visit
    with to_close.app.state.db.session() as s:
        assert s.get(Visit, 1).status == "no_show"


def test_a_bad_status_value_redirects_instead_of_500ing(to_close):
    assert to_close.post("/visits/1/status",
                         data={"value": "elfelejtette"}).status_code == 303


def test_a_visit_that_is_gone_redirects(to_close):
    assert to_close.get("/visits/999/close").status_code == 303
    assert to_close.post("/visits/999/close",
                         data={"findings": "", "note": ""}).status_code == 303


def test_omitting_findings_does_not_wipe_them(to_close):
    """close() reads None as "leave it alone" and "" as "clear it". A caller
    that never sends the field, the API or a partial htmx post, must not wipe
    the column."""
    to_close.post("/visits/1/close", data={"findings": "benőtt köröm",
                                           "note": "reszelés"})
    to_close.post("/visits/1/close", data={"price_1": "20,00"})
    from app.models import Visit
    with to_close.app.state.db.session() as s:
        visit = s.get(Visit, 1)
        assert visit.findings == "benőtt köröm"
        assert visit.items[0].unit_price_cents == 2000


def test_every_error_screen_actually_renders(to_close):
    """Each of these stops at the Location header in the other tests, so the
    page they redirect to has never been drawn."""
    for key, text in [
        ("treatment_price_invalid", "Az ár nem értelmezhető"),
        ("visit_slot_taken", "Az idősávot közben elfoglalta"),
        ("visit_bad_status", "Ismeretlen állapot"),
    ]:
        page = to_close.get(f"/visits/1/close?error={key}")
        assert page.status_code == 200
        assert text in page.text, key
    # and an unknown key renders no banner at all
    assert 'class="error"' not in to_close.get("/visits/1/close?error=S").text


def test_a_bad_status_value_says_so_rather_than_visit_gone(to_close):
    r = to_close.post("/visits/1/status", data={"value": "elfelejtette"})
    assert r.headers["location"] == "/visits/1/close?error=visit_bad_status"


def test_removing_a_treatment_from_the_screen(to_close):
    to_close.post("/settings/treatments",
                  data={"name": "Géllakk", "duration_min": "30",
                        "price_eur": "18,00"})
    to_close.post("/visits/1/treatments", data={"treatment_id": "2"})
    r = to_close.post("/visits/1/items/2/remove")
    assert r.headers["location"] == "/visits/1/close"
    # the name still appears in the add-a-treatment select, so assert on the
    # line's own remove form rather than on the word
    page = to_close.get("/visits/1/close").text
    assert "/visits/1/items/2/remove" not in page
    assert "/visits/1/items/1/remove" in page

    # and the last one stays put
    r = to_close.post("/visits/1/items/1/remove")
    assert r.headers["location"].endswith("error=visit_needs_treatment")


# ---------- phase 2: selling a product on a visit ----------

def _sellable(client, name="Krém", price_cents=850, stock_qty=4):
    from app.services import products, stock
    with client.app.state.db.session() as s:
        p = products.create(s, name, "tubus", created_by="1",
                            sale_price_cents=price_cents)
        if stock_qty:
            stock.record(s, p.id, stock_qty, "purchase", created_by="1",
                         unit_cost_cents=500)
        return p.id


def test_a_product_can_be_sold_at_the_close(to_close):
    from app.services import stock
    krem_id = _sellable(to_close)
    to_close.post("/visits/1/products", data={"product_id": krem_id, "qty": "1"})
    to_close.post("/visits/1/close", data={"findings": "", "note": ""})
    with to_close.app.state.db.session() as s:
        assert stock.quantity(s, krem_id) == 3.0


def test_the_sale_price_is_frozen_on_the_line(to_close):
    """Same rule as a Treatment, and frozen earlier: the price is snapshotted
    when the product is added, not at the close, because close() skips every
    item whose kind is not treatment. Raising the shelf price next month must
    not rewrite what this client paid today."""
    from app.models import Visit
    from app.services import products
    krem_id = _sellable(to_close)
    to_close.post("/visits/1/products", data={"product_id": krem_id, "qty": "2"})
    to_close.post("/visits/1/close", data={"findings": "", "note": ""})
    with to_close.app.state.db.session() as s:
        products.update(s, krem_id, sale_price_cents=1200)
    with to_close.app.state.db.session() as s:
        item = next(i for i in s.get(Visit, 1).items if i.kind == "product")
        assert item.unit_price_cents == 850
        assert item.qty == 2.0


def test_a_product_with_no_sale_price_cannot_be_sold(to_close):
    """Not for sale is not the same as free. Without the guard a consumable
    would land on the bill at zero and the client pay nothing for it."""
    from app.models import Visit
    from app.services import products
    with to_close.app.state.db.session() as s:
        lakk_id = products.create(s, "Lakk", "flakon", created_by="1").id
    r = to_close.post("/visits/1/products",
                      data={"product_id": lakk_id, "qty": "1"})
    assert "error=" in r.headers["location"]
    with to_close.app.state.db.session() as s:
        assert [i for i in s.get(Visit, 1).items if i.kind == "product"] == []


def test_a_sold_product_can_be_taken_off_again(to_close):
    from app.models import Visit
    from app.services import stock
    krem_id = _sellable(to_close)
    to_close.post("/visits/1/products", data={"product_id": krem_id, "qty": "1"})
    to_close.post("/visits/1/close", data={"findings": "", "note": ""})
    with to_close.app.state.db.session() as s:
        item_id = next(i.id for i in s.get(Visit, 1).items
                       if i.kind == "product")
    to_close.post(f"/visits/1/items/{item_id}/remove")
    to_close.post("/visits/1/close", data={"findings": "", "note": ""})
    with to_close.app.state.db.session() as s:
        assert stock.quantity(s, krem_id) == 4.0


def test_the_total_covers_treatments_and_products(to_close):
    from app.models import Visit
    from app.services import visits
    krem_id = _sellable(to_close)
    to_close.post("/visits/1/products", data={"product_id": krem_id, "qty": "2"})
    to_close.post("/visits/1/close", data={"findings": "", "note": ""})
    with to_close.app.state.db.session() as s:
        visit = s.get(Visit, 1)
        # one 25,00 EUR treatment plus two tubes at 8,50
        assert visits.total_cents(visit) == 2500 + 1700
    assert "42,00 EUR" in to_close.get("/visits/1/close").text


def test_an_archived_product_is_not_offered_and_not_addable(to_close):
    from app.services import products
    krem_id = _sellable(to_close)
    with to_close.app.state.db.session() as s:
        products.archive(s, krem_id)
    assert "Krém" not in to_close.get("/visits/1/close").text
    r = to_close.post("/visits/1/products",
                      data={"product_id": krem_id, "qty": "1"})
    assert "error=" in r.headers["location"]


def test_a_mistyped_quantity_says_so_instead_of_500ing(to_close):
    krem_id = _sellable(to_close)
    r = to_close.post("/visits/1/products",
                      data={"product_id": krem_id, "qty": "kettő"})
    assert "error=" in r.headers["location"]


def test_selling_a_negative_quantity_is_refused(to_close):
    """A negative sale would put stock back on the shelf and take money off
    the bill, which is a refund the app has no concept of."""
    krem_id = _sellable(to_close)
    r = to_close.post("/visits/1/products",
                      data={"product_id": krem_id, "qty": "-1"})
    assert "error=" in r.headers["location"]
