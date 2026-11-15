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
def _app(tmp_path, monkeypatch):
    """The real app, reloaded on a throwaway database.

    app.main reads the environment at import, so the reload has to come after
    monkeypatch.
    """
    from app import security
    from app.models import User

    monkeypatch.setenv("HAZTARTAS_DATA", str(tmp_path))
    monkeypatch.setenv("HAZTARTAS_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("HAZTARTAS_HTTPS_ONLY", "0")   # TestClient speaks http
    import app.main
    importlib.reload(app.main)

    # Test-only routes: the guards need somewhere to guard.
    @app.main.app.get("/_guarded")
    def _guarded(user: User = Depends(security.require_user)):
        return {"name": user.name}

    @app.main.app.get("/_adult")
    def _adult(user: User = Depends(security.require_adult)):
        return {"name": user.name}

    @app.main.app.get("/_json")
    def _json(user: User = Depends(security.require_user_json)):
        return {"name": user.name}

    return app.main.app


def _seed(app, username, name, role):
    from app import security
    from app.models import User
    with app.state.db.session() as s:
        s.add(User(name=name, username=username, role=role,
                   password_hash=security.hash_password(PASSWORD)))


def _login(app, username):
    c = TestClient(app, follow_redirects=False)   # own cookie jar
    c.post("/login", data={"username": username, "password": PASSWORD})
    return c


@pytest.fixture
def client(_app):
    """Logged out. Runs lifespan (migrations, engine, templates)."""
    with TestClient(_app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def users(_app):
    """Three users, one app, one database; lifespan stays up for the test."""
    with TestClient(_app):
        _seed(_app, "anna", "Anna", "adult")
        _seed(_app, "bela", "Béla", "adult")
        _seed(_app, "cili", "Cili", "child")
        yield _app


@pytest.fixture
def adult(users):
    return _login(users, "anna")


@pytest.fixture
def adult2(users):
    return _login(users, "bela")


@pytest.fixture
def child(users):
    return _login(users, "cili")
