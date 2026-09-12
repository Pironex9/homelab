"""The Product catalogue: the things she buys, counts, and sometimes resells.

A Product is a bottle, a roll, a box, never millilitres, because the receipt
says "one bottle, EUR 12" and converting it is her arithmetic to do at every
purchase.

There is no `active` flag next to `archived_at`. The spec lists both; two
flags for one idea drift, and the archive/unarchive pair is the one the client
screen already uses.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product
from app.services import timeutil

# Field names arrive from a form, so update() writes only these. Without the
# whitelist a crafted field would reach created_by, archived_at or id.
_FIELDS = frozenset({"name", "unit", "min_stock", "sale_price_cents"})


def _by_name():
    """SQLite's BINARY collation sorts every accented initial after Z, so a
    name starting with one lands below every unaccented name. fold() is the
    same UDF the client and treatment lists use."""
    return func.fold(Product.name)


def list_all(session: Session, include_archived: bool = False) -> list[Product]:
    stmt = select(Product)
    if not include_archived:
        stmt = stmt.where(Product.archived_at.is_(None))
    return list(session.scalars(stmt.order_by(_by_name())))


def for_sale(session: Session) -> list[Product]:
    """The products that may be added to a Visit. sale_price_cents IS NULL
    means "I only use this", and an archived product is off every list."""
    return list(session.scalars(
        select(Product)
        .where(Product.archived_at.is_(None),
               Product.sale_price_cents.isnot(None))
        .order_by(_by_name())))


def get(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise LookupError(f"no product {product_id}")
    return product


def create(session: Session, name: str, unit: str, created_by: str,
           min_stock: float = 0.0,
           sale_price_cents: int | None = None) -> Product:
    name, unit = name.strip(), unit.strip()
    if not name:
        raise ValueError("a product needs a name")
    if not unit:
        # An empty unit renders as a bare number on the stock screen, and she
        # cannot tell three bottles from three millilitres.
        raise ValueError("a product needs a unit")
    if float(min_stock) < 0:
        raise ValueError("a minimum stock cannot be negative")
    product = Product(name=name, unit=unit, min_stock=float(min_stock),
                      sale_price_cents=sale_price_cents, created_by=created_by,
                      created_at=timeutil.to_utc_iso(timeutil.local_now()))
    session.add(product)
    session.flush()
    return product


def update(session: Session, product_id: int, **fields) -> Product:
    bad = set(fields) - _FIELDS
    if bad:
        raise ValueError(f"not an editable product field: {sorted(bad)}")
    product = get(session, product_id)
    for key, value in fields.items():
        setattr(product, key, value)
    session.flush()
    return product


def archive(session: Session, product_id: int) -> None:
    """Off the lists, all its movements kept. Products are never deleted:
    historical Stock Movements and Visit Items point at them."""
    get(session, product_id).archived_at = \
        timeutil.to_utc_iso(timeutil.local_now())
    session.flush()


def unarchive(session: Session, product_id: int) -> None:
    get(session, product_id).archived_at = None
    session.flush()
