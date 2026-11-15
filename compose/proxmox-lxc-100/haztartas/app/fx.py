"""ECB reference rates: parse, store, look up, convert."""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_UP, Decimal
from typing import Awaitable, Callable

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from .models import FxRate

log = logging.getLogger("haztartas.fx")

ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
INTERVAL_SECONDS = 24 * 60 * 60
_NS = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}


def parse_ecb(xml: bytes) -> list[tuple[str, str, Decimal]]:
    """(date, currency, rate per 1 EUR). EUR itself is not in the feed."""
    root = ET.fromstring(xml)
    rows = []
    for day in root.findall("e:Cube/e:Cube", _NS):
        for c in day.findall("e:Cube", _NS):
            rows.append((day.attrib["time"], c.attrib["currency"],
                         Decimal(c.attrib["rate"])))
    return rows


def store(session, rows) -> int:
    """Upsert; returns the number of rows written."""
    for date, currency, rate in rows:
        stmt = insert(FxRate).values(date=date, currency=currency, rate=str(rate))
        session.execute(stmt.on_conflict_do_update(
            index_elements=["date", "currency"], set_={"rate": stmt.excluded.rate}))
    return len(rows)


def rate_for(session, day: str, currency: str) -> Decimal | None:
    """Latest rate on or before `day` (weekends and holidays use the last fixing)."""
    if currency == "EUR":
        return Decimal(1)
    rate = session.scalar(
        select(FxRate.rate)
        .where(FxRate.currency == currency, FxRate.date <= day)
        .order_by(FxRate.date.desc()).limit(1))
    return Decimal(rate) if rate is not None else None


def to_eur_minor(amount_minor: int, rate: Decimal) -> int:
    return int((Decimal(amount_minor) / rate).quantize(Decimal(1), ROUND_HALF_UP))


async def _fetch() -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(ECB_URL)
        resp.raise_for_status()
        return resp.content


async def daily_task(db, fetch: Callable[[], Awaitable[bytes]] = _fetch) -> None:
    """Fetch at start and every 24 h. The 90-day file backfills any gap."""
    while True:
        try:
            body = await fetch()
            with db.session() as s:
                n = store(s, parse_ecb(body))
            log.info("stored %d ECB rates", n)
        except Exception:  # a failed fetch must not kill the app
            log.exception("ECB rate fetch failed")
        await asyncio.sleep(INTERVAL_SECONDS)
