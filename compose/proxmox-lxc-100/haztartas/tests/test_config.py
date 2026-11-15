import pytest
from app import config


def test_blank_secret_refuses_to_start(monkeypatch):
    """docker compose always sets the variable, so absent is not the failure
    mode that happens in practice: empty is."""
    monkeypatch.setenv("HAZTARTAS_SECRET_KEY", "")
    with pytest.raises(RuntimeError, match="HAZTARTAS_SECRET_KEY"):
        config.load()


def test_loads_with_the_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("HAZTARTAS_SECRET_KEY", "key")
    monkeypatch.setenv("HAZTARTAS_DATA", str(tmp_path))
    s = config.load()
    assert s.db_path == tmp_path / "db.sqlite"
    assert s.backup_dir == tmp_path / "backup"
    assert s.media_dir == tmp_path / "media"
    assert s.https_only is True
