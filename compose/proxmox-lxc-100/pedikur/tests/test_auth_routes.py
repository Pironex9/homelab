"""The login routes through the real app, including the guard.

Nothing else exercises app.state wiring, the session cookie flags the spec
requires, or the two different redirects require_user has to produce.
"""
import importlib

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app import security
from app.models import User

PASSWORD = "jelszo-tesztre"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PEDIKUR_DATA", str(tmp_path))
    monkeypatch.setenv("PEDIKUR_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("PEDIKUR_API_TOKEN", "test-token")
    monkeypatch.setenv("PEDIKUR_HTTPS_ONLY", "0")   # TestClient speaks http
    import app.main
    importlib.reload(app.main)

    # There is no guarded route until task 3, so the guard gets one here.
    @app.main.app.get("/_guarded")
    def _guarded(user: User = Depends(security.require_user)):
        return {"name": user.name}

    with TestClient(app.main.app, follow_redirects=False) as c:
        with c.app.state.db.session() as s:
            s.add(User(name="Teszt", username="ancsi", is_admin=1,
                       password_hash=security.hash_password(PASSWORD)))
        yield c


def test_health_needs_no_session(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.text == "ok"


def test_login_form_renders(client):
    r = client.get("/login")
    assert r.status_code == 200
    assert 'name="password"' in r.text


def test_wrong_password_is_401_and_sets_no_cookie(client):
    r = client.post("/login", data={"username": "ancsi", "password": "rossz"})
    assert r.status_code == 401
    assert "session" not in r.cookies


def test_login_sets_a_session_cookie_with_the_required_flags(client):
    r = client.post("/login",
                    data={"username": "ancsi", "password": PASSWORD})
    assert r.status_code == 303
    assert r.headers["location"] == "/"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "max-age=1209600" in cookie      # 14 days, per the spec
    assert "secure" not in cookie           # PEDIKUR_HTTPS_ONLY=0 in this test


def test_guarded_route_redirects_a_browser_and_serves_a_session(client):
    assert client.get("/_guarded").status_code == 303
    assert client.get("/_guarded").headers["location"] == "/login"

    client.post("/login", data={"username": "ancsi", "password": PASSWORD})
    r = client.get("/_guarded")
    assert r.status_code == 200
    assert r.json() == {"name": "Teszt"}


def test_guarded_route_answers_htmx_with_hx_redirect(client):
    """A 303 would make htmx follow it and swap the whole login page into
    whatever fragment target asked for it."""
    r = client.get("/_guarded", headers={"HX-Request": "true"})
    assert r.status_code == 401
    assert r.headers["hx-redirect"] == "/login"


def test_logout_clears_the_session(client):
    client.post("/login", data={"username": "ancsi", "password": PASSWORD})
    assert client.post("/logout").status_code == 303
    assert client.get("/_guarded").status_code == 303


def test_openapi_is_not_published(client):
    assert client.get("/openapi.json").status_code == 404
