import importlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.sqlite"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The real app, on a throwaway database.

    app.main reads the environment at import, so the reload has to come after
    monkeypatch. TestClient as a context manager is what runs lifespan, which
    is where migrations, the engine and the template globals are set up.
    """
    monkeypatch.setenv("HAZTARTAS_DATA", str(tmp_path))
    monkeypatch.setenv("HAZTARTAS_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("HAZTARTAS_HTTPS_ONLY", "0")   # TestClient speaks http
    import app.main
    importlib.reload(app.main)

    with TestClient(app.main.app, follow_redirects=False) as c:
        yield c
