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
from sqlalchemy.orm import Session

from app.models import User

MAX_FAILED = 5
LOCK_MINUTES = 15

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_locked(user: User) -> bool:
    if not user.locked_until:
        return False
    return datetime.fromisoformat(user.locked_until) > _now()


def attempt_login(session: Session, username: str, password: str) -> User | None:
    """Return the user on success, None on failure. Counts failures and locks
    the account for LOCK_MINUTES after MAX_FAILED of them."""
    user = session.query(User).filter_by(username=username).one_or_none()
    if user is None:
        # Hash anyway so a missing username does not answer faster than a
        # wrong password.
        _hasher.hash(password)
        return None
    if _is_locked(user):
        return None
    try:
        _hasher.verify(user.password_hash, password)
    except (VerifyMismatchError, VerificationError):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED:
            user.locked_until = (_now() + timedelta(minutes=LOCK_MINUTES)).isoformat()
        session.flush()
        return None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    user.failed_logins = 0
    user.locked_until = None
    session.flush()
    return user


def current_user(request: Request) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    db = request.app.state.db
    with db.session() as s:
        return s.get(User, user_id)


def require_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER,
                            headers={"Location": "/login"})
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user
