from datetime import datetime, timedelta, timezone

import pytest

from app import migrate, security
from app.db import Database
from app.models import User


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def _make_user(db, username="ancsi", password="jelszo-tesztre"):
    with db.session() as s:
        user = User(name="Teszt", username=username,
                    password_hash=security.hash_password(password),
                    is_admin=0)
        s.add(user)
    return username, password


def test_hash_is_argon2id_and_verifies(db):
    username, password = _make_user(db)
    with db.session() as s:
        user = s.query(User).filter_by(username=username).one()
        assert user.password_hash.startswith("$argon2id$")
        assert security.attempt_login(s, username, password) is not None


def test_wrong_password_counts_up_and_locks_after_five(db):
    username, _ = _make_user(db)
    with db.session() as s:
        for _ in range(5):
            assert security.attempt_login(s, username, "rossz") is None
        user = s.query(User).filter_by(username=username).one()
        assert user.failed_logins == 5
        assert user.locked_until is not None


def test_locked_user_is_refused_even_with_the_right_password(db):
    username, password = _make_user(db)
    with db.session() as s:
        user = s.query(User).filter_by(username=username).one()
        user.locked_until = (datetime.now(timezone.utc)
                             + timedelta(minutes=15)).isoformat()
        s.flush()
        assert security.attempt_login(s, username, password) is None


def test_successful_login_clears_the_counter(db):
    username, password = _make_user(db)
    with db.session() as s:
        security.attempt_login(s, username, "rossz")
        assert security.attempt_login(s, username, password) is not None
        user = s.query(User).filter_by(username=username).one()
        assert user.failed_logins == 0
        assert user.locked_until is None
