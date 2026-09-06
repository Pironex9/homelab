"""The week grid through the real app."""
from datetime import datetime

import pytest

from app.services import timeutil


@pytest.fixture
def week(logged_in):
    logged_in.post("/clients", data={"name": "Kovács Anna", "phone": ""})
    logged_in.post("/settings/treatments",
                   data={"name": "Pedikűr", "duration_min": "45",
                         "price_eur": "25,00"})
    logged_in.post("/visits/new", data={
        "client_id": "1", "start": "2026-09-07T10:00", "end": "",
        "treatment_ids": ["1"]})
    return logged_in


def test_the_calendar_needs_a_session(client):
    assert client.get("/calendar").status_code == 303


def test_the_week_draws_the_visit_and_the_bookable_slots(week):
    page = week.get("/calendar?day=2026-09-07").text
    assert "Kovács Anna" in page
    assert "10:00" in page
    assert 'href="/visits/new?start=2026-09-07T09:00"' in page
    # 10:00 is taken, so the grid still offers the slot underneath the block;
    # what must be there is the link back to closing it
    assert 'href="/visits/1/close"' in page


def test_any_day_of_the_week_anchors_to_its_monday(week):
    for day in ("2026-09-07", "2026-09-09", "2026-09-13"):
        page = week.get(f"/calendar?day={day}").text
        assert "2026. 09. 07." in page, day


def test_a_broken_day_parameter_falls_back_to_this_week(week):
    """A stale link or a hand-edited URL is a bad link, not a 500."""
    r = week.get("/calendar?day=tegnap")
    assert r.status_code == 200
    monday = timeutil.local_now().date()
    assert str(monday.year) in r.text


def test_the_closed_weekend_offers_no_slots(week):
    page = week.get("/calendar?day=2026-09-07").text
    assert "start=2026-09-12T" not in page      # Saturday
    assert "start=2026-09-13T" not in page      # Sunday
    assert "Zárva" in page


def test_the_grid_shows_the_dot_but_never_the_alert_wording(week):
    week.post("/clients/1", data={
        "name": "Kovács Anna", "phone": "", "email": "", "address": "",
        "alert": "cukorbeteg", "notes": ""})
    page = week.get("/calendar?day=2026-09-07").text
    assert "alert-dot" in page
    assert "cukorbeteg" not in page


def test_the_previous_and_next_links_move_a_week(week):
    page = week.get("/calendar?day=2026-09-07").text
    assert 'href="/calendar?day=2026-08-31"' in page
    assert 'href="/calendar?day=2026-09-14"' in page
