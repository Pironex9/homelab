import re

from fastapi import APIRouter, Depends, Request

from app import clock
from app.models import User
from app.security import require_user
from app.services import home

router = APIRouter()
_MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


@router.get("/")
def index(request: Request, month: str | None = None,
          user: User = Depends(require_user)):
    today = clock.today()
    if month is None or not _MONTH.fullmatch(month):
        month = today[:7]
    with request.app.state.db.session() as s:
        ctx = home.build(s, user, month, today)
    return request.app.state.templates.TemplateResponse(request, "home.html", ctx)
