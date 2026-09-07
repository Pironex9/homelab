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


def _today_at(hour: int, minute: int = 0) -> str:
    """A fixed hour on today's date. An offset from now would put a "+2 hours"
    visit on tomorrow whenever the suite runs after 22:00, and the failure
    would read as a Today-window bug rather than a test one."""
    return timeutil.local_now().strftime(f"%Y-%m-%dT{hour:02d}:{minute:02d}")


def test_today_needs_a_session(client):
    assert client.get("/").status_code == 303


def test_an_empty_day_says_so(practice):
    assert "Ma nincs bejegyzett látogatás" in practice.get("/").text


def test_todays_visits_are_listed_with_their_time(practice):
    practice.post("/visits/new", data={
        "client_id": "1", "start": _today_at(9), "end": "",
        "treatment_ids": ["1"]})
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


def test_a_walk_in_is_closed_immediately(practice):
    """Spec section 5: a walk-in is immediately done. Leaving it planned means
    one interruption puts her on the unclosed banner and, because the interval
    counts done Visits only, the client on the Recall List weeks early."""
    practice.post("/walk-in", data={"client_id": "1", "treatment_ids": ["1"]})
    from app.models import Visit
    with practice.app.state.db.session() as s:
        visit = s.get(Visit, 1)
        assert visit.status == "done"
        assert visit.closed_at is not None
        assert visit.items[0].unit_price_cents == 2500
    assert "lezáratlan látogatás" not in practice.get("/").text


def test_a_walk_in_walks_past_two_back_to_back_bookings(practice):
    """One hop is not enough: the probe window is half open, so a 45 minute
    walk-in at 10:00 found only the 10:00-10:45 booking and was moved onto the
    10:45 one. Back to back is the normal shape of her day."""
    # anchored on now, because that is where a walk-in starts
    assert practice.post("/visits/new", data={
        "client_id": "1", "start": _at(0), "end": "",
        "treatment_ids": ["1"]}).status_code == 303
    assert practice.post("/visits/new", data={
        "client_id": "2", "start": _at(45), "end": "",
        "treatment_ids": ["1"]}).status_code == 303

    r = practice.post("/walk-in", data={"client_id": "1",
                                        "treatment_ids": ["1"]})
    assert r.headers["location"] == "/visits/3/close"
    from app.models import Visit
    with practice.app.state.db.session() as s:
        second, walkin = s.get(Visit, 2), s.get(Visit, 3)
        assert walkin.starts_at >= second.ends_at


def test_every_error_the_today_screen_can_show_actually_renders(practice):
    for key, text in [
        ("visit_needs_treatment", "Válassz legalább egy kezelést"),
        ("visit_client_missing", "Ez a kliens már nem foglalható"),
        ("visit_treatment_missing", "A választott kezelés már nem létezik"),
        ("slot_taken", "Ez az idősáv már foglalt"),
        ("visit_gone", "Ez a látogatás már nem létezik"),
        ("visit_time_invalid", "nem értelmezhető"),
    ]:
        page = practice.get(f"/?error={key}")
        assert page.status_code == 200, key
        assert text in page.text, key
    assert 'class="error"' not in practice.get("/?error=weekdays").text


def test_the_alert_wording_never_reaches_the_today_screen(practice):
    """The route hands full Visit rows to the template, so the rule that only
    the colour travels rests on template discipline alone."""
    practice.post("/clients/1", data={
        "name": "Kovács Anna", "phone": "", "email": "", "address": "",
        "alert": "cukorbeteg", "notes": ""})
    practice.post("/visits/new", data={
        "client_id": "1", "start": _today_at(9), "end": "",
        "treatment_ids": ["1"]})
    page = practice.get("/").text
    assert "alert-dot" in page
    assert "cukorbeteg" not in page


def test_a_soft_deleted_visit_is_not_on_today(practice):
    practice.post("/visits/new", data={
        "client_id": "1", "start": _today_at(9), "end": "",
        "treatment_ids": ["1"]})
    from app.models import Visit
    with practice.app.state.db.session() as s:
        s.get(Visit, 1).deleted_at = "2026-09-06T10:00:00Z"
    assert "Ma nincs bejegyzett látogatás" in practice.get("/").text
