"""Runtime settings, read once from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    secret_key: str
    api_token: str
    tz: str = "Europe/Bratislava"

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
        secret_key=os.environ["PEDIKUR_SECRET_KEY"],
        api_token=os.environ["PEDIKUR_API_TOKEN"],
        tz=os.environ.get("TZ", "Europe/Bratislava"),
    )
