import pytest
from app import config


def test_blank_secret_refuses_to_start(monkeypatch):
    """docker compose always sets the variable, so absent is not the failure
    mode that happens in practice: empty is."""
    monkeypatch.setenv("PEDIKUR_SECRET_KEY", "")
    monkeypatch.setenv("PEDIKUR_API_TOKEN", "token")
    with pytest.raises(RuntimeError, match="PEDIKUR_SECRET_KEY"):
        config.load()


def test_loads_with_both_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("PEDIKUR_SECRET_KEY", "key")
    monkeypatch.setenv("PEDIKUR_API_TOKEN", "token")
    monkeypatch.setenv("PEDIKUR_DATA", str(tmp_path))
    s = config.load()
    assert s.db_path == tmp_path / "db.sqlite"
    assert s.backup_dir == tmp_path / "backup"
    assert s.media_dir == tmp_path / "media"
