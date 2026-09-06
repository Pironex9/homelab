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
    assert "Ez a kliens már nem létezik" in r.text

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
