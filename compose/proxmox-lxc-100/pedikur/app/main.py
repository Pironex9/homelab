from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import backup, config, migrate
from app.db import Database
from app.routers import auth

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = _settings
    migrate.run(settings.db_path, backup_dir=settings.backup_dir)
    app.state.settings = settings
    app.state.db = Database(settings.db_path)
    app.state.templates = Jinja2Templates(directory=BASE_DIR / "templates")
    task = asyncio.create_task(
        backup.nightly_task(settings.db_path, settings.backup_dir))
    yield
    task.cancel()


_settings = config.load()   # once, at import: the middleware needs it early

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
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


@app.get("/health")
def health() -> PlainTextResponse:
    return PlainTextResponse("ok")
