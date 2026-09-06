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
    from app.models import Client, Visit
    with logged_in.app.state.db.session() as s:
        s.add(Client(name="Kovács Anna", created_by="1",
                     created_at="2026-09-06T10:00:00Z"))
        s.flush()
        s.add(Visit(client_id=1, starts_at="2026-09-01T07:00:00Z",
                    ends_at="2026-09-01T08:00:00Z", status="done",
                    findings="benőtt köröm", created_by="1",
                    created_at="2026-09-01T06:00:00Z"))

    page = logged_in.get("/clients/1").text
    assert "2026. 09. 01." in page      # 07:00 UTC is still 1 September local
    assert "benőtt köröm" in page
    assert "Még nincs lezárt látogatás" not in page
