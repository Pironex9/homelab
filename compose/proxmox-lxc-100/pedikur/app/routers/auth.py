from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.strings.hu import S

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "login.html", {"error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = request.app.state.db
    templates = request.app.state.templates
    with db.session() as s:
        user, error = security.attempt_login(s, username, password)
        if user is None:
            return templates.TemplateResponse(
                request, "login.html",
                {"error": S[error]}, status_code=401)
        request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
