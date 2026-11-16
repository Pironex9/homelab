"""Admin commands. There is no mail server, so password reset lives here.

    docker compose exec haztartas python -m app.cli create-user anna "Anna" --role adult
    docker compose exec haztartas python -m app.cli reset-password anna
"""
from __future__ import annotations

import getpass
import sys

from app import config, migrate, security
from app.db import Database
from app.models import User, Wallet

MIN_PASSWORD = 8


def _db() -> Database:
    settings = config.load()
    migrate.run(settings.db_path, backup_dir=settings.backup_dir)
    return Database(settings.db_path)


def _ask_password(prompt: str = "Password: ") -> str:
    """getpass returns "" on an empty line, which hashes and stores happily.
    This is the only account creation path for an app holding household finances."""
    password = getpass.getpass(prompt)
    if len(password) < MIN_PASSWORD:
        sys.exit(f"Password must be at least {MIN_PASSWORD} characters.")
    if password != getpass.getpass("Repeat: "):
        sys.exit("Passwords do not match.")
    return password


def create_user(username: str, name: str, role: str) -> None:
    if role not in ("adult", "child"):
        sys.exit("Role must be adult or child.")
    password = _ask_password()
    with _db().session() as s:
        if s.query(User).filter_by(username=username).one_or_none():
            sys.exit(f"User {username} already exists.")
        user = User(name=name, username=username, role=role,
                    password_hash=security.hash_password(password))
        s.add(user)
        s.flush()
        if role == "child":
            # Same transaction: a child without a wallet has nowhere to book.
            s.add(Wallet(name=f"{name} zsebpénze", owner_user_id=user.id))
    print(f"Created {username} (role={role}).")


def reset_password(username: str) -> None:
    password = _ask_password("New password: ")
    with _db().session() as s:
        user = s.query(User).filter_by(username=username).one_or_none()
        if user is None:
            sys.exit(f"No such user: {username}")
        user.password_hash = security.hash_password(password)
        user.failed_logins = 0
        user.locked_until = None
    print(f"Password reset for {username}.")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["create-user", username, name, "--role", role]:
            create_user(username, name, role)
        case ["reset-password", username]:
            reset_password(username)
        case _:
            sys.exit("usage: create-user <username> <name> --role adult|child "
                     "| reset-password <username>")
