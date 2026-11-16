import pytest

from app import cli, config, migrate
from app.db import Database
from app.models import User, Wallet


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("HAZTARTAS_DATA", str(tmp_path))
    monkeypatch.setenv("HAZTARTAS_SECRET_KEY", "x")
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "hosszu-jelszo-1")
    return Database(config.load().db_path)


def _wallets(db, username):
    with db.session() as s:
        user = s.query(User).filter_by(username=username).one()
        return user, s.query(Wallet).filter_by(owner_user_id=user.id).all()


def test_child_gets_wallet_on_create(env):
    cli.create_user("cili", "Cili", "child")
    user, wallets = _wallets(env, "cili")
    assert user.role == "child"
    assert [w.name for w in wallets] == ["Cili zsebpénze"]


def test_adult_gets_no_wallet(env):
    cli.create_user("anna", "Anna", "adult")
    user, wallets = _wallets(env, "anna")
    assert user.role == "adult"
    assert wallets == []


def test_duplicate_username_exits(env):
    cli.create_user("anna", "Anna", "adult")
    with pytest.raises(SystemExit):
        cli.create_user("anna", "Anna", "adult")


def test_bad_role_exits(env):
    with pytest.raises(SystemExit):
        cli.create_user("x", "X", "admin")


def test_short_password_exits(env, monkeypatch):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "rovid")
    with pytest.raises(SystemExit):
        cli.create_user("anna", "Anna", "adult")


def test_reset_password_clears_lock(env):
    cli.create_user("anna", "Anna", "adult")
    with env.session() as s:
        u = s.query(User).filter_by(username="anna").one()
        u.failed_logins = 5
        u.locked_until = "2999-01-01T00:00:00+00:00"
    cli.reset_password("anna")
    user, _ = _wallets(env, "anna")
    assert user.failed_logins == 0 and user.locked_until is None


def test_eight_character_password_is_accepted(env, monkeypatch):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "nyolcbet")
    cli.create_user("csaba", "Csaba", "adult")


def test_seven_character_password_exits(env, monkeypatch):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "hetbetu")
    with pytest.raises(SystemExit):
        cli.create_user("csaba", "Csaba", "adult")
