"""The stock screen: what is on the shelf, and the three movements a human may
type. purchase comes from the expense form and consumption and sale from the
close path, so neither is offered here."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.services import products, stock, treatments
from app.strings.hu import S

router = APIRouter(prefix="/stock")

# A whitelist, not a bare S lookup: the value comes from the query string, so
# S.get(error) would let ?error=weekdays render the repr of a Python list.
_ERRORS = frozenset({
    "stock_qty_invalid", "stock_qty_zero", "stock_cost_invalid",
    "stock_reason_invalid", "product_name_required", "product_unit_required",
})

MAX_QTY = 100_000   # a pedicure practice, not a warehouse


def parse_qty(text: str) -> float:
    """"3", "3,5" or "-2" -> a float. Decimal first, so "1e999" and "nan"
    cannot reach float() and become inf."""
    cleaned = (text or "").strip().replace(",", ".")
    if not cleaned:
        raise ValueError("empty quantity")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"not a quantity: {text!r}") from None
    if not value.is_finite() or abs(value) > MAX_QTY:
        raise ValueError(f"quantity out of range: {text!r}")
    return float(value)


def _error(key: str | None) -> str | None:
    return S[key] if key in _ERRORS else None


def _back(error: str) -> RedirectResponse:
    return RedirectResponse(f"/stock?error={error}", status_code=303)


@router.get("")
def index(request: Request, error: str | None = None, archived: bool = False,
          user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        levels = stock.levels(s, include_archived=archived)
        # Which products have never been bought, so the screen can say why
        # their margin will be empty rather than leaving it a mystery.
        # ponytail: one query per product, at a few dozen products. Fold it
        # into a grouped query in stock.levels() if the screen ever feels slow.
        no_price = {lv.product.id for lv in levels
                    if stock.last_cost_cents(s, lv.product.id) == 0}
        return request.app.state.templates.TemplateResponse(
            request, "stock.html",
            {"user": user, "tab": "more", "levels": levels,
             "no_price": no_price, "archived": archived,
             "reasons": [(r, S[f"stock_reason_{r}"])
                         for r in stock.MANUAL_REASONS],
             "error": _error(error)})


@router.post("/products")
def create(request: Request,
           name: str = Form(...), unit: str = Form(...),
           min_stock: str = Form("0"),
           sale_price_eur: str = Form(""),
           opening_qty: str = Form(""),
           opening_cost_eur: str = Form(""),
           user: User = Depends(security.require_user)):
    """The product and its opening movement are written in one session, so a
    mistyped opening price leaves neither behind. A product created with its
    opening quantity silently dropped is worse than a refused form: nothing on
    the screen would say the stock is wrong."""
    try:
        minimum = parse_qty(min_stock) if min_stock.strip() else 0.0
    except ValueError:
        return _back("stock_qty_invalid")
    if minimum < 0:
        # Checked here and not left to products.create: its ValueError would
        # fall into the name/unit branch below and show the wrong message.
        return _back("stock_qty_invalid")
    sale_cents = None
    if sale_price_eur.strip():
        try:
            sale_cents = treatments.parse_price(sale_price_eur)
        except ValueError:
            return _back("stock_cost_invalid")
    qty = cost = None
    if opening_qty.strip():
        try:
            qty = parse_qty(opening_qty)
        except ValueError:
            return _back("stock_qty_invalid")
        if abs(qty) < stock.QTY_EPSILON:
            return _back("stock_qty_zero")
        try:
            cost = (treatments.parse_price(opening_cost_eur)
                    if opening_cost_eur.strip() else 0)
        except ValueError:
            return _back("stock_cost_invalid")

    try:
        with request.app.state.db.session() as s:
            product = products.create(s, name, unit, created_by=str(user.id),
                                      min_stock=minimum,
                                      sale_price_cents=sale_cents)
            if qty is not None:
                stock.record(s, product.id, qty, "opening",
                             created_by=str(user.id), unit_cost_cents=cost)
    except ValueError as exc:
        key = ("product_unit_required" if "unit" in str(exc)
               else "product_name_required")
        return _back(key)
    return RedirectResponse("/stock", status_code=303)


@router.post("/{product_id}/movement")
def movement(request: Request, product_id: int,
             qty: str = Form(...), reason: str = Form(...),
             cost_eur: str = Form(""),
             user: User = Depends(security.require_user)):
    if reason not in stock.MANUAL_REASONS:
        return _back("stock_reason_invalid")
    try:
        amount = parse_qty(qty)
    except ValueError:
        return _back("stock_qty_invalid")
    if abs(amount) < stock.QTY_EPSILON:
        return _back("stock_qty_zero")
    # Waste takes stock off the shelf whichever way she types it. A correction
    # keeps its sign, because that is the only way to correct downwards.
    if reason == "waste":
        amount = -abs(amount)
    try:
        cost = treatments.parse_price(cost_eur) if cost_eur.strip() else None
    except ValueError:
        return _back("stock_cost_invalid")
    try:
        with request.app.state.db.session() as s:
            if cost is None:
                # An outbound movement with no price typed is charged at what
                # the stock cost, not at zero, or the waste is free.
                cost = stock.last_cost_cents(s, product_id)
            stock.record(s, product_id, amount, reason,
                         created_by=str(user.id), unit_cost_cents=cost)
    except (LookupError, ValueError):
        return RedirectResponse("/stock", status_code=303)
    return RedirectResponse("/stock", status_code=303)


@router.post("/{product_id}/archive")
def archive(request: Request, product_id: int,
            user: User = Depends(security.require_user)):
    _toggle(request, product_id, products.archive)
    return RedirectResponse("/stock", status_code=303)


@router.post("/{product_id}/unarchive")
def unarchive(request: Request, product_id: int,
              user: User = Depends(security.require_user)):
    _toggle(request, product_id, products.unarchive)
    return RedirectResponse("/stock?archived=true", status_code=303)


def _toggle(request: Request, product_id: int, action) -> None:
    """A missing id is a stale page, not a server fault: the list reloads
    without it rather than showing a stack trace."""
    try:
        with request.app.state.db.session() as s:
            action(s, product_id)
    except LookupError:
        pass
