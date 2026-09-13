"""The expense screen. One form: date, vendor, amount, category, note, and
optionally one line item that also brings the goods into stock."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.routers import stock as stock_routes
from app.services import expenses, products, timeutil, treatments
from app.strings.hu import S

router = APIRouter(prefix="/expenses")

# A whitelist, not a bare S lookup: the value comes from the query string, so
# S.get(error) would let ?error=weekdays render the repr of a Python list.
_ERRORS = frozenset({
    "expense_date_invalid", "expense_amount_invalid",
    "expense_category_invalid", "expense_line_invalid",
})


def _back(error: str) -> RedirectResponse:
    return RedirectResponse(f"/expenses?error={error}", status_code=303)


@router.get("")
def index(request: Request, error: str | None = None,
          user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = expenses.recent(s)
        # Shown so a receipt whose lines do not add up to its total is
        # visible. Not enforced at write time: she may have bought a coffee on
        # the same receipt, and a form that refuses the real receipt is a form
        # she stops filling in.
        line_totals = {e.id: expenses.line_total_cents(s, e.id) for e in rows}
        return request.app.state.templates.TemplateResponse(
            request, "expenses.html",
            {"user": user, "tab": "more", "expenses": rows,
             "line_totals": line_totals,
             "categories": [(c, S[f"category_{c}"])
                            for c in expenses.CATEGORIES],
             "products": products.list_all(s),
             # today in local time, not UTC: near midnight in summer they are
             # different days, and the receipt in her hand carries the local one
             "today": timeutil.local_now().date().isoformat(),
             "error": S[error] if error in _ERRORS else None})


@router.post("")
def create(request: Request,
           date: str = Form(...), category: str = Form(...),
           amount_eur: str = Form(...), vendor: str = Form(""),
           note: str = Form(""),
           line_product_id: str = Form(""), line_qty: str = Form(""),
           line_cost_eur: str = Form(""),
           user: User = Depends(security.require_user)):
    try:
        amount = treatments.parse_price(amount_eur)
    except ValueError:
        return _back("expense_amount_invalid")

    lines: list[tuple[int, float, int]] = []
    if line_product_id.strip() and line_qty.strip():
        try:
            lines.append((int(line_product_id),
                          stock_routes.parse_qty(line_qty),
                          treatments.parse_price(line_cost_eur)
                          if line_cost_eur.strip() else 0))
        except ValueError:
            return _back("expense_line_invalid")

    try:
        with request.app.state.db.session() as s:
            expenses.create(s, date, category, amount, created_by=str(user.id),
                            vendor=vendor, note=note, lines=lines)
    except LookupError:
        # a product that is gone: the page was stale, not the server broken
        return _back("expense_line_invalid")
    except ValueError as exc:
        text = str(exc)
        if "calendar date" in text:
            return _back("expense_date_invalid")
        if "category" in text:
            return _back("expense_category_invalid")
        if "amount out of range" in text or "negative" in text:
            return _back("expense_amount_invalid")
        return _back("expense_line_invalid")
    return RedirectResponse("/expenses", status_code=303)


@router.post("/{expense_id}/delete")
def delete(request: Request, expense_id: int,
           user: User = Depends(security.require_user)):
    """A missing id is a stale page, not a server fault: the list reloads
    without it rather than showing a stack trace."""
    try:
        with request.app.state.db.session() as s:
            expenses.delete(s, expense_id, created_by=str(user.id))
    except LookupError:
        pass
    return RedirectResponse("/expenses", status_code=303)
