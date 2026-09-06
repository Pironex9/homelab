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
        assert security.attempt_login(s, username, password)[0] is not None


def test_wrong_password_counts_up_and_locks_after_five(db):
    """One session per attempt, the way HTTP requests arrive. Doing all five
    inside one session would pass even if the counter were never committed."""
    username, _ = _make_user(db)
    for _ in range(5):
        with db.session() as s:
            assert security.attempt_login(s, username, "rossz")[0] is None
    with db.session() as s:
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
        user, error = security.attempt_login(s, username, password)
        assert user is None
        assert error == security.LOGIN_LOCKED


def test_an_expired_lock_clears_the_counter(db):
    """Otherwise failed_logins stays at MAX_FAILED and the next single wrong
    password re-locks the account, fifteen minutes at a time, forever."""
    username, password = _make_user(db)
    with db.session() as s:
        user = s.query(User).filter_by(username=username).one()
        user.failed_logins = 5
        user.locked_until = (datetime.now(timezone.utc)
                             - timedelta(minutes=1)).isoformat()
        s.flush()

    with db.session() as s:
        assert security.attempt_login(s, username, "rossz")[1] == \
            security.LOGIN_FAILED
        user = s.query(User).filter_by(username=username).one()
        assert user.failed_logins == 1
        assert user.locked_until is None

    with db.session() as s:
        assert security.attempt_login(s, username, password)[0] is not None


def test_successful_login_clears_the_counter(db):
    username, password = _make_user(db)
    with db.session() as s:
        security.attempt_login(s, username, "rossz")
        assert security.attempt_login(s, username, password)[0] is not None
        user = s.query(User).filter_by(username=username).one()
        assert user.failed_logins == 0
        assert user.locked_until is None


def test_unknown_username_is_a_plain_failure(db):
    _make_user(db)
    with db.session() as s:
        user, error = security.attempt_login(s, "nincs-ilyen", "barmi")
        assert user is None
        assert error == security.LOGIN_FAILED


def test_user_attributes_survive_the_session_closing(db):
    """security.current_user hands the request a detached instance. It only
    works because Database uses expire_on_commit=False; without it every
    guarded route raises DetachedInstanceError on the first attribute read."""
    _make_user(db)
    with db.session() as s:
        user = s.query(User).filter_by(username="ancsi").one()
    assert user.is_admin == 0
    assert user.name == "Teszt"


def test_parallel_wrong_passwords_lock_the_account(db):
    """Ten threads, and the account ends up locked at exactly MAX_FAILED.

    The read-modify-write this replaced landed 1 of 10 and never locked at
    all, measured. Now the transactions serialise, so attempts six to ten see
    the lock the fifth one set and return without counting: five is the right
    number, not ten."""
    import threading

    username, _ = _make_user(db)

    def attempt():
        with db.session() as s:
            security.attempt_login(s, username, "rossz")

    threads = [threading.Thread(target=attempt) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with db.session() as s:
        user = s.query(User).filter_by(username=username).one()
        assert user.failed_logins == security.MAX_FAILED
        assert user.locked_until is not None
