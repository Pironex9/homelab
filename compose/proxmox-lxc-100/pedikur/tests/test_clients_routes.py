"""The client screens through the real app.

The rule worth a test of its own: the alert wording never reaches a list
screen, only the fact that one exists. Everything else here is the usual
"what does a mistyped form do".
"""


def test_clients_needs_a_session(client):
    assert client.get("/clients").status_code == 303


def test_create_a_client_lands_on_the_card(logged_in):
    r = logged_in.post("/clients", data={"name": "Kovács Anna",
                                         "phone": "0900111222"})
    assert r.status_code == 303
    assert r.headers["location"] == "/clients/1"
    page = logged_in.get("/clients/1").text
    assert "Kovács Anna" in page
    assert "0900111222" in page


def test_an_empty_name_says_so_instead_of_creating_a_nameless_client(logged_in):
    r = logged_in.post("/clients", data={"name": "   ", "phone": ""})
    assert r.headers["location"] == "/clients?error=client_name_required"
    assert "A kliensnek kell egy név" in logged_in.get(r.headers["location"]).text


def test_the_alert_wording_never_reaches_the_list_screen(logged_in):
    logged_in.post("/clients", data={"name": "Kovács Anna", "phone": ""})
    logged_in.post("/clients/1", data={
        "name": "Kovács Anna", "phone": "", "email": "", "address": "",
        "alert": "cukorbeteg, véralvadásgátló", "notes": ""})

    for url in ("/clients", "/clients/search?q=kovacs"):
        page = logged_in.get(url).text
        assert "cukorbeteg" not in page, url
        assert "véralvadásgátló" not in page, url
        assert "alert-dot" in page, url          # the dot is there instead

    card = logged_in.get("/clients/1").text
    assert "cukorbeteg, véralvadásgátló" in card


def test_search_without_accents_finds_the_accented_name(logged_in):
    logged_in.post("/clients", data={"name": "Tóth Örs", "phone": ""})
    assert "Tóth Örs" in logged_in.get("/clients/search?q=toth ors").text
    assert "Nincs találat" in logged_in.get("/clients/search?q=zzz").text


def test_the_search_partial_is_a_fragment_not_a_page(logged_in):
    body = logged_in.get("/clients/search?q=").text
    assert "<ul" in body
    assert "<html" not in body
    assert "tabbar" not in body


def test_a_missing_client_redirects_instead_of_404ing(logged_in):
    r = logged_in.get("/clients/999")
    assert r.status_code == 303
    assert r.headers["location"] == "/clients"


def test_the_history_list_renders_a_closed_visit(logged_in):
    """The localdate filter is resolved when Jinja compiles the template, so a
    missing one breaks the card whether or not any visit exists."""
    from app.models import Client, Treatment, Visit, VisitItem
    with logged_in.app.state.db.session() as s:
        s.add(Client(name="Kovács Anna", created_by="1",
                     created_at="2026-09-06T10:00:00Z"))
        s.add(Treatment(name="Pedikűr", duration_min=45, price_cents=2500,
                        created_by="1"))
        s.flush()
        s.add(Visit(client_id=1, starts_at="2026-09-01T07:00:00Z",
                    ends_at="2026-09-01T08:00:00Z", status="done",
                    findings="benőtt köröm", created_by="1",
                    created_at="2026-09-01T06:00:00Z"))
        s.flush()
        # with an item, so the template dereferences item.treatment.name and
        # the lazy load actually happens; without one that path never runs and
        # a DetachedInstanceError would go unnoticed
        s.add(VisitItem(visit_id=1, kind="treatment", treatment_id=1, qty=1,
                        unit_price_cents=2500))

    page = logged_in.get("/clients/1").text
    assert "2026. 09. 01." in page      # 07:00 UTC is still 1 September local
    assert "benőtt köröm" in page
    assert "Pedikűr" in page
    assert "Még nincs lezárt látogatás" not in page


def test_archive_and_unarchive_from_the_card(logged_in):
    """clients.archive existed with no way to reach it from any screen."""
    logged_in.post("/clients", data={"name": "Kovács Anna", "phone": ""})
    assert "Kovács Anna" in logged_in.get("/clients").text

    r = logged_in.post("/clients/1/archive")
    assert r.headers["location"] == "/clients/1"
    assert "Kovács Anna" not in logged_in.get("/clients").text
    card = logged_in.get("/clients/1").text
    assert "Archiválva" in card
    assert "Visszahozás" in card

    logged_in.post("/clients/1/unarchive")
    assert "Kovács Anna" in logged_in.get("/clients").text


def test_editing_a_client_to_a_blank_name_says_so(logged_in):
    logged_in.post("/clients", data={"name": "Kovács Anna", "phone": ""})
    r = logged_in.post("/clients/1", data={
        "name": "  ", "phone": "", "email": "", "address": "",
        "alert": "", "notes": ""})
    assert r.headers["location"] == "/clients/1?error=client_name_required"
    assert "A kliensnek kell egy név" in logged_in.get(r.headers["location"]).text
    with logged_in.app.state.db.session() as s:
        from app.models import Client
        assert s.get(Client, 1).name == "Kovács Anna"


def test_editing_a_client_that_is_gone_redirects_to_the_list(logged_in):
    r = logged_in.post("/clients/999", data={
        "name": "X", "phone": "", "email": "", "address": "",
        "alert": "", "notes": ""})
    assert r.headers["location"] == "/clients"


def test_the_archived_toggle_brings_a_hidden_client_back(logged_in):
    """Both entry points take the flag: the full page for a no-htmx reload and
    the fragment the checkbox actually fires."""
    logged_in.post("/clients", data={"name": "Kovács Anna", "phone": ""})
    logged_in.post("/clients/1/archive")
    assert "Kovács Anna" not in logged_in.get("/clients").text

    page = logged_in.get("/clients?archived=true").text
    assert "Kovács Anna" in page
    assert "Archiválva" in page          # the pill, so the row reads as retired

    assert "Kovács Anna" in logged_in.get(
        "/clients/search?q=&archived=true").text
    assert "Kovács Anna" not in logged_in.get("/clients/search?q=").text


def test_the_history_shows_what_was_done_not_only_what_was_found(logged_in):
    """visit.note had a textarea on the close screen and no reader anywhere,
    so everything typed into "Amit csináltam" was write-only."""
    from app.models import Client, Treatment, Visit, VisitItem
    with logged_in.app.state.db.session() as s:
        s.add(Client(name="Kovács Anna", created_by="1",
                     created_at="2026-09-06T10:00:00Z"))
        s.add(Treatment(name="Pedikűr", duration_min=45, price_cents=2500,
                        created_by="1"))
        s.flush()
        s.add(Visit(client_id=1, starts_at="2026-09-01T07:00:00Z",
                    ends_at="2026-09-01T08:00:00Z", status="done",
                    findings="benőtt köröm", note="levágva, fertőtlenítve",
                    created_by="1", created_at="2026-09-01T06:00:00Z"))
        s.flush()
        s.add(VisitItem(visit_id=1, kind="treatment", treatment_id=1, qty=1,
                        unit_price_cents=2500))

    page = logged_in.get("/clients/1").text
    assert "benőtt köröm" in page
    assert "levágva, fertőtlenítve" in page
    assert "Amit találtam" in page and "Amit csináltam" in page
