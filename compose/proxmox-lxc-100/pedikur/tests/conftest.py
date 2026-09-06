import importlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

PASSWORD = "jelszo-tesztre"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.sqlite"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The real app, on a throwaway database, with one admin already created.

    app.main reads the environment at import, so the reload has to come after
    monkeypatch. TestClient as a context manager is what runs lifespan, which
    is where migrations, the engine and the template globals are set up.
    """
    from app import security
    from app.models import User

    monkeypatch.setenv("PEDIKUR_DATA", str(tmp_path))
    monkeypatch.setenv("PEDIKUR_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("PEDIKUR_API_TOKEN", "test-token")
    monkeypatch.setenv("PEDIKUR_HTTPS_ONLY", "0")   # TestClient speaks http
    import app.main
    importlib.reload(app.main)

    # Test-only route: the guard needs somewhere to guard.
    @app.main.app.get("/_guarded")
    def _guarded(user: User = Depends(security.require_user)):
        return {"name": user.name}

    with TestClient(app.main.app, follow_redirects=False) as c:
        with c.app.state.db.session() as s:
            s.add(User(name="Teszt", username="ancsi", is_admin=1,
                       password_hash=security.hash_password(PASSWORD)))
        yield c


@pytest.fixture
def logged_in(client):
    client.post("/login", data={"username": "ancsi", "password": PASSWORD})
    return client
