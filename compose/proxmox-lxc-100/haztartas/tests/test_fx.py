import asyncio
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import fx, migrate
from app.db import Database
from app.models import FxRate

FIXTURE = (Path(__file__).parent / "fixtures" / "ecb-90d.xml").read_bytes()


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "t.sqlite"
    migrate.run(path, backup_dir=tmp_path / "bk")
    return Database(path)


def test_parse_ecb():
    rows = fx.parse_ecb(FIXTURE)
    assert len(rows) == 6
    assert ("2026-11-13", "HUF", Decimal("365.6")) in rows
    assert ("2026-11-11", "CZK", Decimal("24.378")) in rows


def test_store_is_idempotent(db):
    rows = fx.parse_ecb(FIXTURE)
    with db.session() as s:
        assert fx.store(s, rows) == 6
    with db.session() as s:
        fx.store(s, rows)
        assert s.scalar(select(func.count()).select_from(FxRate)) == 6


def test_rate_for_weekend_uses_friday(db):
    with db.session() as s:
        fx.store(s, fx.parse_ecb(FIXTURE))
        # 2026-11-15 is a Sunday, 2026-11-13 the Friday before it
        assert fx.rate_for(s, "2026-11-15", "HUF") == Decimal("365.6")
        assert fx.rate_for(s, "2026-11-12", "HUF") == Decimal("364.98")


def test_rate_for_before_any_data_is_none(db):
    with db.session() as s:
        fx.store(s, fx.parse_ecb(FIXTURE))
        assert fx.rate_for(s, "2026-11-10", "HUF") is None


def test_rate_for_unknown_currency_is_none(db):
    with db.session() as s:
        fx.store(s, fx.parse_ecb(FIXTURE))
        assert fx.rate_for(s, "2026-11-13", "XYZ") is None


def test_rate_for_eur_is_one(db):
    with db.session() as s:
        assert fx.rate_for(s, "2026-11-13", "EUR") == Decimal(1)


def test_to_eur_minor_rounds_half_up():
    assert fx.to_eur_minor(36560, Decimal("365.6")) == 100
    assert fx.to_eur_minor(1, Decimal("2")) == 1       # 0.5 rounds up
    assert fx.to_eur_minor(-1, Decimal("2")) == -1     # away from zero


def test_daily_task_fetches_and_stores(db):
    calls = []

    async def fetch():
        calls.append(1)
        return FIXTURE

    async def run():
        task = asyncio.create_task(fx.daily_task(db, fetch=fetch))
        for _ in range(50):
            await asyncio.sleep(0.01)
            if calls:
                break
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    with db.session() as s:
        assert s.scalar(select(func.count()).select_from(FxRate)) == 6


def test_daily_task_survives_fetch_failure(db):
    async def boom():
        raise OSError("no network")

    async def run():
        task = asyncio.create_task(fx.daily_task(db, fetch=boom))
        await asyncio.sleep(0.05)
        assert not task.done()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
