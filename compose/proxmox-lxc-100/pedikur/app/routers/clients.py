from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.services import clients
from app.strings.hu import S

router = APIRouter(prefix="/clients")

# One practitioner has a few hundred clients. The service default of 20 is for
# the type-ahead fragment, not for the screen that has to hold all of them.
LIST_LIMIT = 1000

_ERRORS = frozenset({"client_name_required"})


def _error(key: str | None) -> str | None:
    """A whitelist, not a bare S lookup: the value arrives in the query string
    and S holds lists and unrelated labels."""
    return S[key] if key in _ERRORS else None


@router.get("")
def index(request: Request, q: str = "", error: str | None = None,
          user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = clients.search(s, q, limit=LIST_LIMIT)
        return request.app.state.templates.TemplateResponse(
            request, "clients.html",
            {"user": user, "tab": "clients", "rows": rows, "q": q,
             "error": _error(error)})


@router.get("/search")
def search_partial(request: Request, q: str = "",
                   user: User = Depends(security.require_user)):
    """htmx target: returns only the result list."""
    with request.app.state.db.session() as s:
        rows = clients.search(s, q)
        return request.app.state.templates.TemplateResponse(
            request, "partials/client_search.html", {"rows": rows})


@router.post("")
def create(request: Request, name: str = Form(...), phone: str = Form(""),
           user: User = Depends(security.require_user)):
    try:
        with request.app.state.db.session() as s:
            client = clients.create(s, name, phone.strip() or None,
                                    created_by=str(user.id))
            client_id = client.id
    except ValueError:
        return RedirectResponse("/clients?error=client_name_required",
                                status_code=303)
    return RedirectResponse(f"/clients/{client_id}", status_code=303)


@router.get("/{client_id}")
def card(request: Request, client_id: int, error: str | None = None,
         user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        client = clients.get(s, client_id)
        if client is None:
            return RedirectResponse("/clients", status_code=303)
        visits = clients.history(s, client_id)
        return request.app.state.templates.TemplateResponse(
            request, "client.html",
            {"user": user, "tab": "clients", "client": client, "visits": visits,
             "error": _error(error)})


@router.post("/{client_id}/archive")
def archive(request: Request, client_id: int,
            user: User = Depends(security.require_user)):
    return _toggle(request, client_id, clients.archive)


@router.post("/{client_id}/unarchive")
def unarchive(request: Request, client_id: int,
              user: User = Depends(security.require_user)):
    return _toggle(request, client_id, clients.unarchive)


def _toggle(request: Request, client_id: int, action):
    try:
        with request.app.state.db.session() as s:
            action(s, client_id)
    except LookupError:
        return RedirectResponse("/clients", status_code=303)
    return RedirectResponse(f"/clients/{client_id}", status_code=303)


@router.post("/{client_id}")
def edit(request: Request, client_id: int,
         name: str = Form(...), phone: str = Form(""),
         email: str = Form(""), address: str = Form(""),
         alert: str = Form(""), notes: str = Form(""),
         user: User = Depends(security.require_user)):
    try:
        with request.app.state.db.session() as s:
            clients.update(s, client_id, name=name, phone=phone or None,
                           email=email or None, address=address or None,
                           alert=alert or None, notes=notes or None)
    except ValueError:
        return RedirectResponse(
            f"/clients/{client_id}?error=client_name_required", status_code=303)
    except LookupError:
        return RedirectResponse("/clients", status_code=303)
    return RedirectResponse(f"/clients/{client_id}", status_code=303)
