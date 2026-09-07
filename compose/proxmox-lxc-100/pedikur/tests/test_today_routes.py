"""The Today screen and walk-ins."""
from datetime import timedelta

import pytest

from app.services import timeutil


@pytest.fixture
def practice(logged_in):
    logged_in.post("/clients", data={"name": "Kovács Anna", "phone": ""})
    logged_in.post("/clients", data={"name": "Nagy Eszter", "phone": ""})
    logged_in.post("/settings/treatments",
                   data={"name": "Pedikűr", "duration_min": "45",
                         "price_eur": "25,00"})
    return logged_in


def _at(offset_minutes: int) -> str:
    moment = (timeutil.local_now() + timedelta(minutes=offset_minutes)
              ).replace(second=0, microsecond=0)
    return moment.strftime("%Y-%m-%dT%H:%M")


def test_today_needs_a_session(client):
    assert client.get("/").status_code == 303


def test_an_empty_day_says_so(practice):
    assert "Ma nincs bejegyzett látogatás" in practice.get("/").text


def test_todays_visits_are_listed_with_their_time(practice):
    practice.post("/visits/new", data={
        "client_id": "1", "start": _at(120), "end": "", "treatment_ids": ["1"]})
    page = practice.get("/").text
    assert "Kovács Anna" in page
    assert 'href="/visits/1/close"' in page


def test_a_visit_tomorrow_is_not_on_today(practice):
    practice.post("/visits/new", data={
        "client_id": "1", "start": _at(60 * 26), "end": "",
        "treatment_ids": ["1"]})
    assert "Ma nincs bejegyzett látogatás" in practice.get("/").text


def test_the_unclosed_banner_links_to_the_oldest_one(practice):
    """The banner is only useful if it is also the fix."""
    practice.post("/visits/new", data={
        "client_id": "1", "start": _at(-180), "end": "", "treatment_ids": ["1"]})
    page = practice.get("/").text
    assert "lezáratlan látogatás" in page
    assert 'class="banner-warning" href="/visits/1/close"' in page

    practice.post("/visits/1/close", data={"findings": "", "note": ""})
    assert "lezáratlan látogatás" not in practice.get("/").text


def test_a_walk_in_starts_now_and_lands_on_the_closing_screen(practice):
    r = practice.post("/walk-in", data={"client_id": "1",
                                        "treatment_ids": ["1"]})
    assert r.status_code == 303
    assert r.headers["location"] == "/visits/1/close"


def test_a_walk_in_during_another_visit_starts_after_it(practice):
    practice.post("/walk-in", data={"client_id": "1", "treatment_ids": ["1"]})
    r = practice.post("/walk-in", data={"client_id": "2",
                                        "treatment_ids": ["1"]})
    assert r.headers["location"] == "/visits/2/close"

    from app.models import Visit
    with practice.app.state.db.session() as s:
        first, second = s.get(Visit, 1), s.get(Visit, 2)
        assert second.starts_at == first.ends_at


def test_a_walk_in_that_would_run_into_a_later_booking_starts_after_it(practice):
    """The plan probed only the current minute and then took max() of an empty
    list, which is a 500 whenever the conflict has not started yet."""
    practice.post("/visits/new", data={
        "client_id": "1", "start": _at(15), "end": "", "treatment_ids": ["1"]})
    r = practice.post("/walk-in", data={"client_id": "2",
                                        "treatment_ids": ["1"]})
    assert r.status_code == 303
    from app.models import Visit
    with practice.app.state.db.session() as s:
        booked, walkin = s.get(Visit, 1), s.get(Visit, 2)
        assert walkin.starts_at == booked.ends_at


def test_a_walk_in_with_nothing_ticked_says_so(practice):
    r = practice.post("/walk-in", data={"client_id": "1"})
    assert r.headers["location"] == "/?error=visit_needs_treatment"
    assert "Válassz legalább egy kezelést" in practice.get(r.headers["location"]).text


def test_a_walk_in_for_a_client_that_is_gone_says_so(practice):
    r = practice.post("/walk-in", data={"client_id": "999",
                                        "treatment_ids": ["1"]})
    assert r.headers["location"] == "/?error=visit_client_missing"


def test_the_pwa_shell_is_served(practice):
    assert practice.get("/static/manifest.json").status_code == 200
    assert practice.get("/static/sw.js").status_code == 200
    assert practice.get("/static/icon-192.png").status_code == 200
    assert practice.get("/static/icon-512.png").status_code == 200
    assert "/static/icon-192.png" in practice.get("/").text
