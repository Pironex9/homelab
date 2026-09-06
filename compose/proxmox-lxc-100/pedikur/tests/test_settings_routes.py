"""The settings screens through the real app.

The service tests cover the rules; these cover what a mistyped form does,
which is the part that turns into a 500 when nobody checks.
"""


def test_settings_needs_a_session(client):
    assert client.get("/settings/treatments").status_code == 303
    assert client.post("/settings/treatments",
                       data={"name": "x", "duration_min": "45",
                             "price_eur": "25"}).status_code == 303


def test_create_a_treatment_and_see_it_listed(logged_in):
    r = logged_in.post("/settings/treatments",
                       data={"name": "Pedikűr", "duration_min": "45",
                             "price_eur": "25,00"})
    assert r.status_code == 303
    page = logged_in.get("/settings/treatments").text
    assert "Pedikűr" in page
    assert "25,00 EUR" in page
    assert "45" in page


def test_a_mistyped_price_says_so_instead_of_500ing(logged_in):
    # not "Pedikűr": that is also the app name, which the nav renders
    r = logged_in.post("/settings/treatments",
                       data={"name": "Talpmasszázs", "duration_min": "45",
                             "price_eur": "huszonöt"})
    assert r.status_code == 303
    assert r.headers["location"].endswith("error=treatment_price_invalid")
    page = logged_in.get(r.headers["location"]).text
    assert "Az ár nem értelmezhető" in page
    assert "Talpmasszázs" not in page     # and nothing was created


def test_a_too_short_duration_is_refused(logged_in):
    r = logged_in.post("/settings/treatments",
                       data={"name": "Pedikűr", "duration_min": "0",
                             "price_eur": "25"})
    assert r.headers["location"].endswith("error=treatment_duration_invalid")


def test_deactivate_then_activate_round_trips(logged_in):
    logged_in.post("/settings/treatments",
                   data={"name": "Géllakk", "duration_min": "30",
                         "price_eur": "18"})
    logged_in.post("/settings/treatments/1/deactivate")
    page = logged_in.get("/settings/treatments").text
    assert "Kivezetve" in page
    assert "Visszaállítás" in page

    logged_in.post("/settings/treatments/1/activate")
    page = logged_in.get("/settings/treatments").text
    assert "Kivezetve" not in page


def test_hours_form_shows_the_seeded_week(logged_in):
    page = logged_in.get("/settings/hours").text
    for day in ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek",
                "Szombat", "Vasárnap"]:
        assert day in page
    assert 'value="09:00"' in page
    assert 'value="17:00"' in page


def test_saving_hours_writes_every_day(logged_in):
    data = {}
    for weekday in range(5):
        data[f"start_{weekday}"] = "08:30"
        data[f"end_{weekday}"] = "16:00"
    for weekday in (5, 6):
        data[f"closed_{weekday}"] = "on"
        data[f"start_{weekday}"] = "09:00"
        data[f"end_{weekday}"] = "17:00"
    assert logged_in.post("/settings/hours", data=data).status_code == 303

    from app.models import WorkingHours
    with logged_in.app.state.db.session() as s:
        rows = {r.weekday: r for r in s.query(WorkingHours)
                .filter(WorkingHours.weekday.isnot(None))}
        assert len(rows) == 7
        assert rows[0].start == "08:30" and rows[0].is_closed == 0
        assert rows[6].is_closed == 1


def test_a_closing_time_before_the_opening_is_refused(logged_in):
    """An inverted open day produces an empty calendar column and nothing
    downstream would say why.

    The values differ from the seed and the assertion is on Saturday and
    Sunday, which 002_seed.sql never created: asserting the seeded 09:00 is
    still there would pass even against a loop that wrote the earlier days
    before hitting the bad one."""
    data = {f"start_{d}": "08:00" for d in range(7)}
    data.update({f"end_{d}": "16:00" for d in range(7)})
    data["start_2"], data["end_2"] = "17:00", "09:00"
    r = logged_in.post("/settings/hours", data=data)
    assert r.status_code == 303
    assert "error=hours_end_before_start&day=2" in r.headers["location"]
    assert "Szerda" in logged_in.get(r.headers["location"]).text

    from app.models import WorkingHours
    with logged_in.app.state.db.session() as s:
        rows = {r.weekday: r for r in s.query(WorkingHours)
                .filter(WorkingHours.weekday.isnot(None))}
        assert set(rows) == {0, 1, 2, 3, 4}      # nothing written for 5 and 6
        assert rows[0].start == "09:00"          # and day 0 kept its seed


def test_a_malformed_time_is_refused_instead_of_500ing(logged_in):
    """The schema CHECK fires at commit, inside the session, so an
    IntegrityError would escape the route rather than reach the form."""
    data = {f"start_{d}": "09:00" for d in range(7)}
    data.update({f"end_{d}": "17:00" for d in range(7)})
    data["start_4"] = "9:00"                     # a text fallback, not HH:MM
    r = logged_in.post("/settings/hours", data=data)
    assert r.status_code == 303
    assert "error=hours_time_invalid&day=4" in r.headers["location"]
    assert "Péntek" in logged_in.get(r.headers["location"]).text


def test_saving_hours_says_so(logged_in):
    data = {f"start_{d}": "09:00" for d in range(7)}
    data.update({f"end_{d}": "17:00" for d in range(7)})
    r = logged_in.post("/settings/hours", data=data)
    assert r.headers["location"] == "/settings/hours?saved=1"
    assert "Munkaidő mentve" in logged_in.get(r.headers["location"]).text


def test_an_unknown_error_key_renders_nothing(logged_in):
    """S holds lists and unrelated labels, and the key comes from the URL."""
    page = logged_in.get("/settings/treatments?error=weekdays").text
    assert "Hétfő" not in page
    assert "class=\"error\"" not in page
    page = logged_in.get("/settings/treatments?error=nav_calendar").text
    assert "class=\"error\"" not in page


def test_a_duplicate_treatment_name_is_refused(logged_in):
    for _ in range(2):
        r = logged_in.post("/settings/treatments",
                           data={"name": "Talpmasszázs", "duration_min": "45",
                                 "price_eur": "25"})
    assert r.headers["location"].endswith("error=treatment_name_taken")
    page = logged_in.get(r.headers["location"]).text
    assert "Már van ilyen nevű kezelés" in page
    assert page.count("Talpmasszázs") == 1


def test_toggling_a_treatment_that_is_gone_reloads_the_list(logged_in):
    assert logged_in.post("/settings/treatments/9999/deactivate").status_code == 303
    assert logged_in.post("/settings/treatments/9999/activate").status_code == 303


def test_the_list_sorts_accented_names_where_a_reader_expects_them(logged_in):
    """SQLite's BINARY collation puts every accented initial after Z."""
    for name in ("Zsírozás", "Állapotfelmérés", "Pedikűr"):
        logged_in.post("/settings/treatments",
                       data={"name": name, "duration_min": "30",
                             "price_eur": "10"})
    page = logged_in.get("/settings/treatments").text
    assert (page.index("Állapotfelmérés") < page.index("Pedikűr")
            < page.index("Zsírozás"))
