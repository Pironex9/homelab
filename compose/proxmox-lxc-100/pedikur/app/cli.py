"""Admin commands. There is no mail server, so password reset lives here.

    docker compose exec pedikur python -m app.cli create-user ancsi "Ancsi"
    docker compose exec pedikur python -m app.cli reset-password ancsi
"""
from __future__ import annotations

import getpass
import sys

from app import config, migrate, security
from app.db import Database
from app.models import User


def _db() -> Database:
    settings = config.load()
    migrate.run(settings.db_path, backup_dir=settings.backup_dir)
    return Database(settings.db_path)


def create_user(username: str, name: str, admin: bool) -> None:
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat: "):
        sys.exit("Passwords do not match.")
    with _db().session() as s:
        if s.query(User).filter_by(username=username).one_or_none():
            sys.exit(f"User {username} already exists.")
        s.add(User(name=name, username=username, is_admin=int(admin),
                   password_hash=security.hash_password(password)))
    print(f"Created {username} (admin={admin}).")


def reset_password(username: str) -> None:
    password = getpass.getpass("New password: ")
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
        case ["create-user", username, name]:
            create_user(username, name, admin=False)
        case ["create-user", username, name, "--admin"]:
            create_user(username, name, admin=True)
        case ["reset-password", username]:
            reset_password(username)
        case _:
            sys.exit("usage: create-user <username> <name> [--admin] "
                     "| reset-password <username>")
