"""The login routes through the real app, including the guards."""
from tests.conftest import PASSWORD


def test_health_needs_no_session(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.text == "ok"


def test_login_form_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert 'name="password"' in r.text


def test_wrong_password_is_401_and_sets_no_cookie(users, client):
    r = client.post("/login", data={"username": "anna", "password": "rossz"})
    assert r.status_code == 401
    assert "session" not in r.cookies


def test_login_sets_a_session_cookie_with_the_required_flags(users, client):
    r = client.post("/login", data={"username": "anna", "password": PASSWORD})
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=7776000" in cookie      # 90 days
    assert "secure" not in cookie           # HAZTARTAS_HTTPS_ONLY=0 here


def test_session_cookie_max_age_90_days_and_rolling(adult):
    """Re-issued on every response, so an active device never expires."""
    r = adult.get("/_guarded")
    assert r.status_code == 200
    assert "max-age=7776000" in r.headers["set-cookie"].lower()


def test_guarded_route_redirects_a_browser_and_serves_a_session(users, client):
    assert client.get("/_guarded").status_code == 303
    assert client.get("/_guarded").headers["location"] == "/login"
    client.post("/login", data={"username": "anna", "password": PASSWORD})
    r = client.get("/_guarded")
    assert r.status_code == 200
    assert r.json() == {"name": "Anna"}


def test_guarded_route_answers_htmx_with_hx_redirect(client):
    r = client.get("/_guarded", headers={"HX-Request": "true"})
    assert r.status_code == 401
    assert r.headers["hx-redirect"] == "/login"


def test_require_adult_403_for_child(adult, child):
    assert adult.get("/_adult").status_code == 200
    assert child.get("/_adult").status_code == 403


def test_require_user_json_401_not_303(client):
    for headers in ({}, {"HX-Request": "true"}):
        r = client.get("/_json", headers=headers)
        assert r.status_code == 401
        assert r.json() == {"detail": "login"}
        assert "location" not in r.headers
        assert "hx-redirect" not in r.headers


def test_require_user_json_serves_a_session(child):
    assert child.get("/_json").json() == {"name": "Cili"}


def test_three_clients_share_one_database(adult, adult2, child):
    assert adult.get("/_guarded").json()["name"] == "Anna"
    assert adult2.get("/_guarded").json()["name"] == "Béla"
    assert child.get("/_guarded").json()["name"] == "Cili"


def test_logout_clears_the_session(adult):
    assert adult.post("/logout").status_code == 303
    assert adult.get("/_guarded").status_code == 303


def test_openapi_is_not_published(client):
    assert client.get("/openapi.json").status_code == 404


def test_password_reset_ends_other_sessions(users, adult, child):
    from sqlalchemy import select
    from app import security
    from app.models import User
    assert adult.get("/_guarded").status_code == 200
    with users.state.db.session() as s:
        u = s.scalars(select(User).where(User.username == "anna")).one()
        u.password_hash = security.hash_password("uj-jelszo-tesztre")
    r = adult.get("/_guarded")
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert adult.get("/_json").status_code == 401
    assert child.get("/_guarded").status_code == 200   # others untouched


def test_session_carries_a_fingerprint_not_the_hash(users, adult):
    import base64
    import json
    from sqlalchemy import select
    from app.models import User
    cookie = adult.cookies.get("session")
    raw = cookie.split(".")[0]
    data = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))
    with users.state.db.session() as s:
        h = s.scalars(select(User).where(User.username == "anna")).one().password_hash
    fp = data["pw"]
    assert len(fp) == 16 and fp not in h
