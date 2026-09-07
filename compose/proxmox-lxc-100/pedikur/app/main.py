from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import backup, config, display, migrate
from app.db import Database
from app.services import timeutil
from app.routers import auth, calendar, clients, today, visits
from app.routers import settings as settings_router
from app.strings.hu import S

BASE_DIR = Path(__file__).parent

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = _settings
    migrate.run(settings.db_path, backup_dir=settings.backup_dir)
    app.state.settings = settings
    app.state.db = Database(settings.db_path)
    templates = Jinja2Templates(directory=BASE_DIR / "templates")
    templates.env.globals["S"] = S   # every template needs it; none should be handed it
    # Integer math, not cents / 100: the column is integer cents precisely so
    # no float ever touches money, and this is the last place to reintroduce one.
    templates.env.filters["eur"] = display.eur
    templates.env.filters["localdate"] = timeutil.localdate
    templates.env.filters["localtime"] = timeutil.localtime
    app.state.templates = templates
    task = asyncio.create_task(
        backup.nightly_task(settings.db_path, settings.backup_dir))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


_settings = config.load()   # once, at import: the middleware needs it early

if not _settings.https_only:
    log.warning("PEDIKUR_HTTPS_ONLY=0: session cookies are sent without the "
                "Secure flag. Never do this on the public route.")

# openapi_url off as well as the docs pages: it would publish the whole route
# table, and once the /api/* surface lands it would describe every machine
# write at a path the Pangolin deny rule does not cover.
app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=_settings.secret_key,
    # Secure cookie, so a plain-http origin silently drops it and the login
    # form just reloads. PEDIKUR_HTTPS_ONLY=0 is for reaching the app over
    # http on the LAN or in the screenshot loop, never for the public route.
    https_only=_settings.https_only,
    same_site="lax",
    max_age=14 * 24 * 60 * 60,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(auth.router)
app.include_router(today.router)
app.include_router(calendar.router)
app.include_router(clients.router)
app.include_router(visits.router)
app.include_router(settings_router.router)


@app.get("/health")
def health() -> PlainTextResponse:
    return PlainTextResponse("ok")
