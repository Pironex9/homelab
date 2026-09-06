"""Passwords, sessions and the login throttle.

The app never trusts that it sits behind Pangolin: this login runs even when
an SSO layer has already passed the request. One proxy misconfiguration must
not be the only thing between the internet and Article 9 health data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import User

MAX_FAILED = 5
LOCK_MINUTES = 15

# keys into app.strings.hu.S, so the caller can tell the two apart
LOGIN_FAILED = "login_failed"
LOGIN_LOCKED = "login_locked"

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_locked(user: User) -> bool:
    if not user.locked_until:
        return False
    return datetime.fromisoformat(user.locked_until) > _now()


def _count_failure(session: Session, user: User) -> int:
    """Increment in the database, not in Python.

    `user.failed_logins += 1` reads a snapshot and writes back an absolute
    number, so ten parallel POSTs to /login all read 0 and all write 1, and
    the account never reaches MAX_FAILED. Which is exactly the parallel brute
    force this counter exists to stop.
    """
    session.execute(
        update(User)
        .where(User.id == user.id)
        .values(failed_logins=User.failed_logins + 1)
    )
    session.flush()
    session.refresh(user)
    return user.failed_logins


def attempt_login(session: Session, username: str,
                  password: str) -> tuple[User | None, str | None]:
    """Return (user, None) on success, (None, error_key) on failure.

    The error key separates a wrong password from a locked account. Answering
    "wrong username or password" to someone who is locked out sends her back
    to guessing, and every guess re-arms the lock.
    """
    user = session.query(User).filter_by(username=username).one_or_none()
    if user is None:
        # Hash anyway so a missing username does not answer faster than a
        # wrong password.
        _hasher.hash(password)
        return None, LOGIN_FAILED
    if _is_locked(user):
        # Hash here too. Returning early would make a locked, existing
        # username answer in microseconds while an unknown one takes tens of
        # milliseconds, which is the enumeration oracle the branch above
        # exists to close, only inverted.
        _hasher.hash(password)
        return None, LOGIN_LOCKED
    if user.locked_until:
        # The lock has expired. Clear the counter with it, or failed_logins
        # stays at MAX_FAILED and the next single wrong password re-locks the
        # account, forever, fifteen minutes at a time.
        user.locked_until = None
        user.failed_logins = 0
        session.flush()
    try:
        _hasher.verify(user.password_hash, password)
    except (VerifyMismatchError, VerificationError):
        if _count_failure(session, user) >= MAX_FAILED:
            user.locked_until = (_now() + timedelta(minutes=LOCK_MINUTES)).isoformat()
            session.flush()
            return None, LOGIN_LOCKED
        return None, LOGIN_FAILED
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    user.failed_logins = 0
    user.locked_until = None
    session.flush()
    return user, None


def current_user(request: Request) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    db = request.app.state.db
    with db.session() as s:
        # Readable after the session closes only because Database uses
        # expire_on_commit=False. User has no relationships, so nothing lazy
        # loads off it either.
        return s.get(User, user_id)


def require_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        if request.headers.get("HX-Request"):
            # htmx follows a 303 transparently and would swap the whole login
            # page into whatever fragment target the request named. HX-Redirect
            # navigates instead, and htmx honours it before it looks at the
            # status code.
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                headers={"HX-Redirect": "/login"})
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER,
                            headers={"Location": "/login"})
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user
