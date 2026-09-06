"""Runtime settings, read once from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

GENERATE = 'python -c "import secrets;print(secrets.token_urlsafe(48))"'


def _required(name: str) -> str:
    """Absent and empty are the same failure: docker compose always sets the
    variable, so os.environ[name] alone would let a blank .env through and the
    app would sign every session with an empty key."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is empty or unset. Generate one with: {GENERATE}")
    return value


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    secret_key: str
    api_token: str
    tz: str = "Europe/Bratislava"
    # Session cookies carry Secure by default. Turning it off is for reaching
    # the app over plain http on the LAN or in the screenshot loop: a browser
    # drops a Secure cookie on an http origin, and the login form then just
    # reloads with no error to show for it.
    https_only: bool = True

    @property
    def db_path(self) -> Path:
        return self.data_dir / "db.sqlite"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backup"


def load() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("PEDIKUR_DATA", "/data")),
        secret_key=_required("PEDIKUR_SECRET_KEY"),
        api_token=_required("PEDIKUR_API_TOKEN"),
        tz=os.environ.get("TZ") or "Europe/Bratislava",
        https_only=os.environ.get("PEDIKUR_HTTPS_ONLY", "1") != "0",
    )
