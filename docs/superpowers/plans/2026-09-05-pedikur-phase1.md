# Pedikur Phase 1 Implementation Plan

> **For agentic workers: read this block before invoking any skill.** This plan
> does NOT use superpowers:subagent-driven-development, and does not use
> superpowers:executing-plans either. The execution mode was chosen deliberately
> and is described in "Execution mode" below. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** A working appointment book the practitioner can use instead of her paper diary: log in, keep clients and a treatment price list, see the week, book by clicking an empty slot, and close a visit in one tap.

**Architecture:** One FastAPI container serving server-rendered Jinja templates with htmx, over a single SQLite file in WAL mode. Two routers share one service layer: HTML routes for the UI, `/api/*` JSON routes for scripting. Schema changes are numbered SQL files applied at startup inside a transaction, preceded by an automatic snapshot.

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, SQLAlchemy 2.0 (ORM, `DeclarativeBase` + `Mapped[]`), Jinja2, htmx 2.x, argon2-cffi, itsdangerous, pytest. SQLite via the stdlib driver.

**Spec:** `docs/superpowers/specs/2026-09-05-pedikur-design.md` - read it before starting. Its section 0 lists the whole document set: the glossary, the four ADRs, and the plans for the other phases. When a constraint here looks arbitrary, the reason is usually in an ADR: `0003` receipts stay outside the app, `0004` why the backend is hand-written, `0005` why health data is unencrypted at rest, `0006` why there is no SPA. Terms in **bold** here (Visit, Treatment, Visit Item, Archive, Erase) are defined in the repo root `CONTEXT.md` under "Pedikur" and are used in their glossary sense.

## Execution mode

Chosen on 2026-09-05 after reading Anthropic's own subagent guidance against
the superpowers default. They disagree, and they are not talking about the same
thing: the subagent's value here is the fresh-eyes review, not the
implementation.

**Backend tasks (1, 2, 4, 5, 10): implement inline, then one review subagent.**
These tasks build on each other - the model, then the service, then the routes -
which is precisely the shape Anthropic says not to hand to parallel subagents.
The review is where a fresh context pays: the reviewer does not know which
trade-offs were weighed, so it sees what the implementer has stopped seeing.

Give the reviewer exactly three things and nothing from the working
conversation: the task's diff (`git show`), this task's section of this plan,
and `docs/superpowers/specs/2026-09-05-pedikur-design.md`. Ask it for
correctness and spec compliance. Address the findings, or record in the commit
why a finding was not acted on.

**Frontend tasks (3, 6, 7, 8, 9): implement inline with a screenshot loop, no
subagent.** A fresh subagent cannot see what it rendered and does not remember
the previous screen's decisions, so four screens from four subagents produce
four different-looking screens. The loop is: render, screenshot, look at the
image, fix `app.css`, repeat. The script and its three load-bearing settings
are in Task 3, Step 5.

**Task 3 uses the `impeccable` skill, not `design-taste-frontend`** - the
latter's own SKILL.md excludes dashboards, data tables and multi-step product
UI, which is exactly what this is.

### Where to stop, and where not to

Two checkpoints. Stop, report, and wait for the human at both:

1. **After Task 1**, before starting Task 2. Task 1 writes
   `docker-compose.yml` with `build: .`, and whether Komodo handles a build
   directive in this git-based setup is unverified. Try the deploy now: if it
   does not work, the compose file changes shape (a `ghcr.io` image plus a
   GitHub Actions workflow) and that is far cheaper to find out here than after
   Task 10.
2. **After Task 3**, before starting Task 4. This is the visual gate. Six
   screens will inherit the tokens and the shell. Put the screenshots in front
   of the human and get a yes on the direction; discovering at screen seven
   that the typography is wrong means rewriting all seven.

Between every other task, keep going. Do not ask "shall I continue?" and do not
summarise progress between tasks. Stop only for a blocker: a failing test that
does not yield, a missing dependency, a step in this plan that turns out to be
wrong, or anything destructive or outward-facing.

## Global Constraints

- **Python 3.13** (`python:3.13-slim`). One release behind 3.14.7 deliberately: every dependency has wheels for it.
- **SQLAlchemy 2.0**, not SQLModel. SQLModel is 0.0.39 and pre-1.0; the spec rejected PocketBase for exactly that, and a server-rendered app gets no value from SQLModel's ORM/Pydantic unification.
- **htmx pinned to 2.x**, vendored into `static/`. Not 4.x: 2.x stays `latest` on npm until early 2027, is feature-complete and supported indefinitely.
- **No npm, no bundler, no build step.** CSS and JS are hand-written files served as-is.
- **Money is integer cents**, EUR. Never float. Column names end in `_cents`.
- **All timestamps stored UTC as ISO-8601 text**, rendered in `Europe/Bratislava`. The exception is `working_hours.start`/`end`, which are wall-clock `HH:MM` strings and must never be timezone-converted.
- **Passwords: argon2-cffi, Argon2id.** Not passlib, not pwdlib.
- **Soft delete via `deleted_at`; `archived_at` on client and product.** Nothing in phase 1 hard-deletes.
- **`created_by` on `client`, `treatment`, `visit`**: the user id, or the string `api`.
- **The app never trusts that it sits behind Pangolin.** Its own login always requires a password.
- **The `alert` field's text never appears on a list screen**, only its colour. The text lives inside the client card.
- **Everything committed is English**: code, comments, commit messages. User-facing strings are Hungarian and live in `app/strings/hu.py`.
- **No em dashes anywhere**, in code, comments, docs or UI copy. Plain hyphens.
- **Host port 3010** on LXC 100 (verified free against every compose file in `compose/proxmox-lxc-100/`).

## Out of scope for phase 1

Named so they are decisions, not omissions: products, stock, treatment recipes, expenses, photos and the `attachment` table, Google sync, buffers, free-slot highlighting, the dashboard, the Recall List, and the MCP server. Photos are deferred because they do not help put the paper diary down, and they can arrive in phase 2 without touching the one-tap close path.

## File Structure

```
compose/proxmox-lxc-100/pedikur/
  docker-compose.yml      stack definition, port 3010, volume, healthcheck
  Dockerfile              python:3.13-slim, non-root user, uvicorn entrypoint
  requirements.txt        pinned dependencies
  .env.example            documented, non-secret defaults
  README.md               run, backup and rollback commands
  app/
    __init__.py
    config.py             env -> a frozen settings object
    db.py                 engine, session factory, SQLite pragmas
    migrate.py            snapshot, then apply numbered SQL, then record version
    backup.py             Connection.backup() helper, nightly asyncio task
    models.py             SQLAlchemy declarative models, phase 1 tables only
    security.py           hashing, session, login throttle, route guards
    cli.py                create-user, reset-password
    main.py               app factory, middleware, router mounting, startup
    strings/hu.py         every user-facing string, keyed
    services/
      clients.py          client queries, search, alert rules
      treatments.py       treatment catalogue queries
      visits.py           booking, ends_at rules, the idempotent close
      schedule.py         working hours -> week grid
    routers/
      auth.py             login, logout
      today.py            today screen, walk-in
      calendar.py         week grid
      visits.py           new, edit, close
      clients.py          list, card, create inline
      settings.py         working hours, treatments, users
      api.py              JSON, bearer token
    migrations/
      001_schema.sql      the seven phase 1 tables
      002_seed.sql        working hours, buffer_min, default_interval_days
    templates/            base.html plus one per screen, partials/ for htmx swaps
    static/
      htmx.min.js         vendored 2.x
      tokens.css          colour, type scale, spacing
      app.css             components
      manifest.json, sw.js, icons
  tests/
    conftest.py           temp database fixture
    test_migrate.py
    test_security.py
    test_schedule.py
    test_visits.py
```

Split by responsibility rather than by layer: a router, its service and its
templates change together, so they are named for the same thing. `models.py`
stays one file because at seven tables it is still readable in one screen and
splitting it would spread the foreign keys across files.

---

### Task 1: Stack skeleton, database and the migration runner

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/Dockerfile`
- Create: `compose/proxmox-lxc-100/pedikur/docker-compose.yml`
- Create: `compose/proxmox-lxc-100/pedikur/requirements.txt`
- Create: `compose/proxmox-lxc-100/pedikur/.env.example`
- Create: `compose/proxmox-lxc-100/pedikur/app/{__init__.py,config.py,db.py,backup.py,migrate.py}`
- Create: `compose/proxmox-lxc-100/pedikur/app/migrations/{001_schema.sql,002_seed.sql}`
- Test: `compose/proxmox-lxc-100/pedikur/tests/{conftest.py,test_migrate.py}`

**Interfaces:**
- Produces: `config.settings` (frozen dataclass with `db_path: Path`, `media_dir: Path`, `backup_dir: Path`, `secret_key: str`, `api_token: str`, `tz: str`); `db.engine`, `db.session_scope()` context manager; `backup.snapshot(db_path: Path, dest_dir: Path, tag: str) -> Path`; `migrate.run(db_path: Path) -> list[str]` returning the filenames applied.

- [ ] **Step 1: Write the failing test**

```python
# tests/conftest.py
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.sqlite"
```

```python
# tests/test_migrate.py
import sqlite3
from app import migrate


def test_migrate_creates_schema_and_is_idempotent(db_path, tmp_path):
    first = migrate.run(db_path, backup_dir=tmp_path / "backup")
    assert "001_schema.sql" in first
    assert "002_seed.sql" in first

    con = sqlite3.connect(db_path)
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"user", "client", "treatment", "visit", "visit_item",
            "working_hours", "setting"} <= tables
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    # seeded defaults
    hours = con.execute(
        "SELECT COUNT(*) FROM working_hours WHERE weekday IS NOT NULL").fetchone()[0]
    assert hours == 5
    buffer_min = con.execute(
        "SELECT value FROM setting WHERE key='buffer_min'").fetchone()[0]
    assert buffer_min == "15"
    con.close()

    second = migrate.run(db_path, backup_dir=tmp_path / "backup")
    assert second == []


def test_migrate_snapshots_before_applying(db_path, tmp_path):
    backup_dir = tmp_path / "backup"
    migrate.run(db_path, backup_dir=backup_dir)
    # first run has nothing to snapshot: the file does not exist yet
    assert not list(backup_dir.glob("*.sqlite"))

    (db_path.parent / "003_noop.sql").write_text("SELECT 1;")
    migrate.run(db_path, backup_dir=backup_dir,
                migrations_dir=db_path.parent)
    assert len(list(backup_dir.glob("pre-migration-*.sqlite"))) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd compose/proxmox-lxc-100/pedikur && python -m pytest tests/test_migrate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'` or `AttributeError: module 'app.migrate' has no attribute 'run'`

- [ ] **Step 3: Write `app/config.py`**

```python
"""Runtime settings, read once from the environment."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    secret_key: str
    api_token: str
    tz: str = "Europe/Bratislava"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "db.sqlite"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backup"


def load() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("PEDIKUR_DATA", "/data")),
        secret_key=os.environ["PEDIKUR_SECRET_KEY"],
        api_token=os.environ["PEDIKUR_API_TOKEN"],
        tz=os.environ.get("TZ", "Europe/Bratislava"),
    )
```

`load()` raises `KeyError` when a secret is missing. That is deliberate: a
container that starts with no signing key would issue forgeable sessions, so
it must refuse to start instead.

- [ ] **Step 4: Write `app/backup.py`**

```python
"""SQLite online backup. Never copy a live WAL database with cp."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

KEEP_DAILY = 7


def snapshot(db_path: Path, dest_dir: Path, tag: str = "daily") -> Path | None:
    """Copy the database consistently while it is in use. Returns the path,
    or None when there is no database to copy yet."""
    if not db_path.exists():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / f"{tag}-{stamp}.sqlite"
    source = sqlite3.connect(db_path)
    target = sqlite3.connect(dest)
    try:
        with target:
            source.backup(target)
    finally:
        target.close()
        source.close()
    return dest


def prune(dest_dir: Path, tag: str = "daily", keep: int = KEEP_DAILY) -> None:
    files = sorted(dest_dir.glob(f"{tag}-*.sqlite"), reverse=True)
    for stale in files[keep:]:
        stale.unlink()


async def nightly_task(db_path: Path, dest_dir: Path) -> None:
    """Snapshot once a day. Runs for the life of the process."""
    while True:
        await asyncio.sleep(24 * 60 * 60)
        try:
            snapshot(db_path, dest_dir, tag="daily")
            prune(dest_dir, tag="daily")
        except Exception:  # a failed backup must not kill the app
            pass
```

- [ ] **Step 5: Write `app/migrate.py`**

```python
"""Numbered SQL migrations, applied at startup inside a transaction.

No Alembic: what it would add is downgrade scripts we would never run, and on
SQLite its autogenerate needs render_as_batch=True or it emits statements
SQLite cannot execute. create_all is not an option either - it creates missing
tables and never adds a column to an existing one.

SQLite DDL is transactional, so a migration that fails half way leaves no
half-built schema.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app import backup

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _applied(con: sqlite3.Connection) -> set[str]:
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "  filename TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL DEFAULT (datetime('now'))"
        ")"
    )
    return {row[0] for row in con.execute("SELECT filename FROM schema_version")}


def run(db_path: Path, backup_dir: Path,
        migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every migration newer than the recorded version.

    Returns the filenames applied, oldest first. Empty when up to date.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in migrations_dir.glob("*.sql"))

    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        done = _applied(con)
        pending = [p for p in files if p.name not in done]
        if not pending:
            return []
    finally:
        con.close()

    # Snapshot before touching the schema. Cheap, and it turns a bad migration
    # into seconds of loss rather than falling back to last midnight.
    backup.snapshot(db_path, backup_dir, tag="pre-migration")

    applied: list[str] = []
    con = sqlite3.connect(db_path)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        for path in pending:
            with con:  # one transaction per migration
                con.executescript(path.read_text())
                con.execute(
                    "INSERT INTO schema_version (filename) VALUES (?)",
                    (path.name,),
                )
            applied.append(path.name)
    finally:
        con.close()
    return applied
```

- [ ] **Step 6: Write `app/migrations/001_schema.sql`**

```sql
-- Phase 1 tables. Times are ISO-8601 UTC text, except working_hours.start
-- and working_hours.end which are wall-clock "HH:MM" and must never be
-- timezone-converted. Money is integer cents, EUR.

CREATE TABLE user (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until  TEXT
);

CREATE TABLE client (
    id                     INTEGER PRIMARY KEY,
    name                   TEXT NOT NULL,
    phone                  TEXT,
    email                  TEXT,
    address                TEXT,
    alert                  TEXT,   -- health warning, shown only inside the card
    notes                  TEXT,
    interval_override_days INTEGER,
    archived_at            TEXT,
    erased_at              TEXT,
    created_by             TEXT NOT NULL,
    created_at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_client_name ON client (name);

CREATE TABLE treatment (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    duration_min INTEGER NOT NULL,
    price_cents  INTEGER NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    created_by   TEXT    NOT NULL
);

CREATE TABLE visit (
    id         INTEGER PRIMARY KEY,
    client_id  INTEGER NOT NULL REFERENCES client (id),
    starts_at  TEXT    NOT NULL,   -- ISO-8601 UTC
    ends_at    TEXT    NOT NULL,   -- ISO-8601 UTC, only ever grows on its own
    status     TEXT    NOT NULL DEFAULT 'planned'
               CHECK (status IN ('planned', 'done', 'cancelled', 'no_show')),
    findings   TEXT,               -- what was observed
    note       TEXT,               -- what was done
    deleted_at TEXT,
    created_by TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_visit_window ON visit (starts_at, ends_at);
CREATE INDEX idx_visit_client ON visit (client_id, starts_at);

CREATE TABLE visit_item (
    id               INTEGER PRIMARY KEY,
    visit_id         INTEGER NOT NULL REFERENCES visit (id),
    kind             TEXT    NOT NULL CHECK (kind IN ('treatment', 'product')),
    treatment_id     INTEGER REFERENCES treatment (id),
    product_id       INTEGER,     -- phase 2
    qty              REAL    NOT NULL DEFAULT 1,
    unit_price_cents INTEGER NOT NULL,
    CHECK (
        (kind = 'treatment' AND treatment_id IS NOT NULL AND product_id IS NULL)
        OR
        (kind = 'product' AND product_id IS NOT NULL AND treatment_id IS NULL)
    )
);
CREATE INDEX idx_visit_item_visit ON visit_item (visit_id);

CREATE TABLE working_hours (
    id        INTEGER PRIMARY KEY,
    weekday   INTEGER,        -- 0 = Monday .. 6 = Sunday, the recurring default
    date      TEXT,           -- YYYY-MM-DD, overrides that one day
    start     TEXT NOT NULL,  -- wall clock "HH:MM"
    end       TEXT NOT NULL,  -- wall clock "HH:MM"
    is_closed INTEGER NOT NULL DEFAULT 0,
    CHECK ((weekday IS NULL) <> (date IS NULL))
);
CREATE UNIQUE INDEX idx_working_hours_weekday ON working_hours (weekday)
    WHERE weekday IS NOT NULL;
CREATE UNIQUE INDEX idx_working_hours_date ON working_hours (date)
    WHERE date IS NOT NULL;

CREATE TABLE setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

- [ ] **Step 7: Write `app/migrations/002_seed.sql`**

```sql
-- Without these the app is broken on arrival: no working hours means an
-- unbounded calendar grid and no bookable day.

INSERT INTO working_hours (weekday, start, end, is_closed) VALUES
    (0, '09:00', '17:00', 0),
    (1, '09:00', '17:00', 0),
    (2, '09:00', '17:00', 0),
    (3, '09:00', '17:00', 0),
    (4, '09:00', '17:00', 0);

INSERT INTO setting (key, value) VALUES
    ('buffer_min', '15'),
    ('default_interval_days', '42');
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd compose/proxmox-lxc-100/pedikur && python -m pytest tests/test_migrate.py -v`
Expected: PASS, 2 tests

- [ ] **Step 9: Write `app/db.py`**

```python
"""Engine and session handling. One writer, so the pragmas do the work."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


def make_engine(db_path: Path):
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"timeout": 5.0},  # SQLite has no pool; this is busy_timeout
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA busy_timeout = 5000")
        cur.execute("PRAGMA synchronous = NORMAL")
        cur.close()

    return engine


class Database:
    def __init__(self, db_path: Path) -> None:
        self.engine = make_engine(db_path)
        self._factory = sessionmaker(bind=self.engine, future=True,
                                     expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
```

- [ ] **Step 10: Write `requirements.txt`, `Dockerfile`, `docker-compose.yml` and `.env.example`**

```
# requirements.txt
fastapi==0.129.*
uvicorn[standard]==0.38.*
sqlalchemy==2.0.*
jinja2==3.1.*
python-multipart==0.0.*
itsdangerous==2.2.*
argon2-cffi==25.*
pytest==8.*
httpx==0.28.*
```

Resolve each `*` to the newest matching release at implementation time and
commit the exact pins produced by `pip freeze` into the file. The ranges here
say which major and minor line is intended, not what to install.

```dockerfile
# Dockerfile
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home --uid 1000 pedikur \
 && mkdir -p /data && chown -R pedikur:pedikur /data /srv
USER pedikur

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--forwarded-allow-ips", "*"]
```

`--forwarded-allow-ips` matters: behind Pangolin and newt, without it the
`Secure` cookie and every redirect break.

```yaml
# docker-compose.yml
services:
  pedikur:
    build: .
    container_name: pedikur
    environment:
      - TZ=${TZ}
      - PEDIKUR_DATA=/data
      - PEDIKUR_SECRET_KEY=${PEDIKUR_SECRET_KEY}
      - PEDIKUR_API_TOKEN=${PEDIKUR_API_TOKEN}
    volumes:
      - ${DOCKER_DATA}/pedikur:/data
    ports:
      - 3010:8000
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
```

```
# .env.example
TZ=Europe/Bratislava
DOCKER_DATA=/srv/docker-data
# Both secrets live in the Komodo Stack Environment, never in git.
# Generate with: python -c "import secrets;print(secrets.token_urlsafe(48))"
PEDIKUR_SECRET_KEY=
PEDIKUR_API_TOKEN=
```

- [ ] **Step 11: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): stack skeleton, SQLite setup and migration runner"
```

---

### Task 2: Authentication, users and the admin CLI

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/app/{models.py,security.py,cli.py,main.py}`
- Create: `compose/proxmox-lxc-100/pedikur/app/strings/{__init__.py,hu.py}`
- Create: `compose/proxmox-lxc-100/pedikur/app/routers/{__init__.py,auth.py}`
- Create: `compose/proxmox-lxc-100/pedikur/app/templates/{base.html,login.html}`
- Test: `compose/proxmox-lxc-100/pedikur/tests/test_security.py`

**Interfaces:**
- Consumes: `db.Database.session()`, `config.load()`, `migrate.run()` from Task 1.
- Produces: `models.User/Client/Treatment/Visit/VisitItem/WorkingHours/Setting`; `security.hash_password(str) -> str`, `security.verify(user, password) -> bool`, `security.attempt_login(session, username, password) -> User | None`, `security.current_user(request) -> User | None`, `security.require_user`, `security.require_admin` (FastAPI dependencies); `main.app`; `main.templates` (a configured `Jinja2Templates`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_security.py
from datetime import datetime, timedelta, timezone

import pytest

from app import migrate, security
from app.db import Database
from app.models import User


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def _make_user(db, username="ancsi", password="jelszo-tesztre"):
    with db.session() as s:
        user = User(name="Teszt", username=username,
                    password_hash=security.hash_password(password),
                    is_admin=0)
        s.add(user)
    return username, password


def test_hash_is_argon2id_and_verifies(db):
    username, password = _make_user(db)
    with db.session() as s:
        user = s.query(User).filter_by(username=username).one()
        assert user.password_hash.startswith("$argon2id$")
        assert security.attempt_login(s, username, password) is not None


def test_wrong_password_counts_up_and_locks_after_five(db):
    username, _ = _make_user(db)
    with db.session() as s:
        for _ in range(5):
            assert security.attempt_login(s, username, "rossz") is None
        user = s.query(User).filter_by(username=username).one()
        assert user.failed_logins == 5
        assert user.locked_until is not None


def test_locked_user_is_refused_even_with_the_right_password(db):
    username, password = _make_user(db)
    with db.session() as s:
        user = s.query(User).filter_by(username=username).one()
        user.locked_until = (datetime.now(timezone.utc)
                             + timedelta(minutes=15)).isoformat()
        s.flush()
        assert security.attempt_login(s, username, password) is None


def test_successful_login_clears_the_counter(db):
    username, password = _make_user(db)
    with db.session() as s:
        security.attempt_login(s, username, "rossz")
        assert security.attempt_login(s, username, password) is not None
        user = s.query(User).filter_by(username=username).one()
        assert user.failed_logins == 0
        assert user.locked_until is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd compose/proxmox-lxc-100/pedikur && python -m pytest tests/test_security.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 3: Write `app/models.py`**

```python
"""Phase 1 tables. The schema of record is app/migrations/001_schema.sql;
these classes mirror it and must be changed together with a new migration.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    is_admin: Mapped[int] = mapped_column(Integer, default=0)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[str | None] = mapped_column(String, nullable=True)


class Client(Base):
    __tablename__ = "client"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    alert: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    interval_override_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived_at: Mapped[str | None] = mapped_column(String, nullable=True)
    erased_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class Treatment(Base):
    __tablename__ = "treatment"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    duration_min: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)
    active: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String)


class Visit(Base):
    __tablename__ = "visit"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"))
    starts_at: Mapped[str] = mapped_column(String)
    ends_at: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="planned")
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)

    client: Mapped[Client] = relationship(lazy="joined")
    items: Mapped[list["VisitItem"]] = relationship(
        back_populates="visit", lazy="selectin")


class VisitItem(Base):
    __tablename__ = "visit_item"
    id: Mapped[int] = mapped_column(primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visit.id"))
    kind: Mapped[str] = mapped_column(String)
    treatment_id: Mapped[int | None] = mapped_column(
        ForeignKey("treatment.id"), nullable=True)
    product_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qty: Mapped[float] = mapped_column(Float, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer)

    visit: Mapped[Visit] = relationship(back_populates="items")
    treatment: Mapped[Treatment | None] = relationship(lazy="joined")


class WorkingHours(Base):
    __tablename__ = "working_hours"
    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    start: Mapped[str] = mapped_column(String)
    end: Mapped[str] = mapped_column(String)
    is_closed: Mapped[int] = mapped_column(Integer, default=0)


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
```

- [ ] **Step 4: Write `app/security.py`**

```python
"""Passwords, sessions and the login throttle.

The app never trusts that it sits behind Pangolin: this login runs even when
an SSO layer has already passed the request. One proxy misconfiguration must
not be the only thing between the internet and Article 9 health data.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models import User

MAX_FAILED = 5
LOCK_MINUTES = 15

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_locked(user: User) -> bool:
    if not user.locked_until:
        return False
    return datetime.fromisoformat(user.locked_until) > _now()


def attempt_login(session: Session, username: str, password: str) -> User | None:
    """Return the user on success, None on failure. Counts failures and locks
    the account for LOCK_MINUTES after MAX_FAILED of them."""
    user = session.query(User).filter_by(username=username).one_or_none()
    if user is None:
        # Hash anyway so a missing username does not answer faster than a
        # wrong password.
        _hasher.hash(password)
        return None
    if _is_locked(user):
        return None
    try:
        _hasher.verify(user.password_hash, password)
    except (VerifyMismatchError, VerificationError):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED:
            user.locked_until = (_now() + timedelta(minutes=LOCK_MINUTES)).isoformat()
        session.flush()
        return None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = _hasher.hash(password)
    user.failed_logins = 0
    user.locked_until = None
    session.flush()
    return user


def current_user(request: Request) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    db = request.app.state.db
    with db.session() as s:
        return s.get(User, user_id)


def require_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER,
                            headers={"Location": "/login"})
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return user
```

`require_admin` guards nothing in phase 1 and that is deliberate: the spec's
admin-only operations are user management, the Google connection and **Erase**,
and none of them has a screen yet. User management is the CLI in Step 9; the
other two arrive in phase 3 and the GDPR work. It is written now because the
first screen that needs it should not also have to invent the guard.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd compose/proxmox-lxc-100/pedikur && python -m pytest tests/test_security.py -v`
Expected: PASS, 4 tests

- [ ] **Step 6: Write `app/strings/hu.py`**

```python
"""Every user-facing string. One language ships; a second is translation."""

S = {
    "app_name": "Pedikur",
    "login_title": "Bejelentkezes",
    "login_user": "Felhasznalonev",
    "login_password": "Jelszo",
    "login_submit": "Belepes",
    "login_failed": "Hibas felhasznalonev vagy jelszo.",
    "login_locked": "A fiok ideiglenesen zarolva. Probald ujra 15 perc mulva.",
    "logout": "Kilepes",
    "nav_today": "Ma",
    "nav_calendar": "Naptar",
    "nav_clients": "Kliensek",
    "nav_more": "Tobb",
}
```

Accents are omitted here on purpose so the file stays ASCII-safe in every
terminal; the implementer replaces them with proper Hungarian accents in one
pass at the end of Task 3, once the font stack is fixed and renders them.

- [ ] **Step 7: Write `app/routers/auth.py`**

```python
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.strings.hu import S

router = APIRouter()


@router.get("/login")
def login_form(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request, "login.html", {"S": S, "error": None})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = request.app.state.db
    templates = request.app.state.templates
    with db.session() as s:
        user = security.attempt_login(s, username, password)
        if user is None:
            return templates.TemplateResponse(
                request, "login.html",
                {"S": S, "error": S["login_failed"]}, status_code=401)
        request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
```

- [ ] **Step 8: Write `app/main.py`**

```python
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
    https_only=True,
    same_site="lax",
    max_age=14 * 24 * 60 * 60,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(auth.router)


@app.get("/health")
def health() -> PlainTextResponse:
    return PlainTextResponse("ok")
```

- [ ] **Step 9: Write `app/cli.py`**

```python
"""Admin commands. There is no mail server, so password reset lives here.

    docker compose exec pedikur python -m app.cli create-user ancsi "Ancsi"
    docker compose exec pedikur python -m app.cli reset-password ancsi
"""
from __future__ import annotations

import getpass
import sys

from app import config, migrate, security
from app.db import Database
from app.models import User


def _db() -> Database:
    settings = config.load()
    migrate.run(settings.db_path, backup_dir=settings.backup_dir)
    return Database(settings.db_path)


def create_user(username: str, name: str, admin: bool) -> None:
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat: "):
        sys.exit("Passwords do not match.")
    with _db().session() as s:
        if s.query(User).filter_by(username=username).one_or_none():
            sys.exit(f"User {username} already exists.")
        s.add(User(name=name, username=username, is_admin=int(admin),
                   password_hash=security.hash_password(password)))
    print(f"Created {username} (admin={admin}).")


def reset_password(username: str) -> None:
    password = getpass.getpass("New password: ")
    with _db().session() as s:
        user = s.query(User).filter_by(username=username).one_or_none()
        if user is None:
            sys.exit(f"No such user: {username}")
        user.password_hash = security.hash_password(password)
        user.failed_logins = 0
        user.locked_until = None
    print(f"Password reset for {username}.")


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["create-user", username, name]:
            create_user(username, name, admin=False)
        case ["create-user", username, name, "--admin"]:
            create_user(username, name, admin=True)
        case ["reset-password", username]:
            reset_password(username)
        case _:
            sys.exit("usage: create-user <username> <name> [--admin] "
                     "| reset-password <username>")
```

- [ ] **Step 10: Write minimal `templates/base.html` and `templates/login.html`**

These are deliberately unstyled. Task 3 is the design pass and will replace the
CSS; writing pretty markup now would mean writing it twice.

```html
<!-- templates/base.html -->
<!doctype html>
<html lang="hu">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{{ S["app_name"] }}{% endblock %}</title>
  <link rel="stylesheet" href="/static/tokens.css">
  <link rel="stylesheet" href="/static/app.css">
  <script src="/static/htmx.min.js" defer></script>
</head>
<body>
  {% block body %}{% endblock %}
</body>
</html>
```

```html
<!-- templates/login.html -->
{% extends "base.html" %}
{% block title %}{{ S["login_title"] }}{% endblock %}
{% block body %}
<main class="login">
  <h1>{{ S["login_title"] }}</h1>
  {% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}
  <form method="post" action="/login">
    <label for="username">{{ S["login_user"] }}</label>
    <input id="username" name="username" autocomplete="username" required>
    <label for="password">{{ S["login_password"] }}</label>
    <input id="password" name="password" type="password"
           autocomplete="current-password" required>
    <button type="submit">{{ S["login_submit"] }}</button>
  </form>
</main>
{% endblock %}
```

Create empty `static/tokens.css` and `static/app.css` so the links resolve, and
vendor htmx 2.x into `static/htmx.min.js`:

```bash
curl -fsSL https://unpkg.com/htmx.org@2/dist/htmx.min.js \
  -o app/static/htmx.min.js
grep -c 'htmx' app/static/htmx.min.js   # sanity check: non-zero
```

- [ ] **Step 11: Verify the container starts and login works end to end**

```bash
cd compose/proxmox-lxc-100/pedikur
export PEDIKUR_DATA=$(mktemp -d) \
       PEDIKUR_SECRET_KEY=$(python -c "import secrets;print(secrets.token_urlsafe(48))") \
       PEDIKUR_API_TOKEN=dev
python -m app.cli create-user admin "Admin" --admin
uvicorn app.main:app --port 8000 &
curl -s localhost:8000/health          # expect: ok
curl -s -i localhost:8000/login | head -1   # expect: HTTP/1.1 200 OK
```

Expected: `ok`, then `200 OK`, and the login form posts to a 303 redirect.

- [ ] **Step 12: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): argon2 auth, login throttle, session and admin CLI"
```

---

### Task 3: Design foundation (frontend, inline, screenshot loop)

This is the visual gate. Every screen after it inherits these decisions, and
nothing after it invents new ones. Do not delegate this task to a subagent: a
subagent cannot see what it rendered, and a later one would not remember what
this one chose.

**REQUIRED SKILL:** invoke `impeccable` before writing any CSS. Do **not** use
`design-taste-frontend` - its own SKILL.md excludes dashboards, data tables and
multi-step product UI, which is exactly what this is.

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/DESIGN.md`
- Create: `compose/proxmox-lxc-100/pedikur/app/static/tokens.css`
- Modify: `compose/proxmox-lxc-100/pedikur/app/static/app.css`
- Modify: `compose/proxmox-lxc-100/pedikur/app/templates/{base.html,login.html}`
- Create: `compose/proxmox-lxc-100/pedikur/scripts/shot.mjs`

**Interfaces:**
- Produces: the token names every later template uses. Later tasks reference
  colours and spacing only through these custom properties, never as literals:
  `--bg`, `--surface`, `--surface-2`, `--ink`, `--ink-muted`, `--line`,
  `--accent`, `--accent-ink`, `--danger`, `--ok`, `--radius`, `--gap-1` through
  `--gap-5`, `--font-sans`, `--step--1` through `--step-3`.
  Also produces the app shell blocks in `base.html`: `{% block body %}` wrapped
  by `<header class="topbar">`, `<main class="content">` and
  `<nav class="tabbar">`.

- [ ] **Step 1: Commit to a direction in writing, before any CSS**

Create `DESIGN.md` answering four questions in one or two sentences each, then
derive the tokens from those answers rather than from habit. Without an
explicit direction a model returns the highest-probability answer, which is
Inter, a purple gradient and a card grid.

```markdown
# Pedikur design direction

**Purpose:** A working tool held in one hand between clients, and read on a
laptop in the evening. Speed of reading beats richness.

**Tone:** Calm and clinical without being cold. It sits in a treatment room,
so it must look clean rather than playful.

**Constraints:** Thumb-reachable primary actions. Legible at arm's length on a
phone. One accent colour, used only for the primary action and today's column.
Red is reserved for the client alert and nothing else, or it stops meaning
anything.

**Differentiation:** This is not the brand of `brand/BRAND.md`. That brand is
the repo owner's public identity, dark and portfolio-tuned; this is someone
else's daily tool and gets its own light, quiet palette.
```

- [ ] **Step 2: Write `static/tokens.css`**

The token set below is complete and runnable as written. Its structure is
fixed; its values are the design decision and are expected to change during the
screenshot loop in step 5.

```css
:root {
  color-scheme: light;

  --bg: #f7f6f4;
  --surface: #ffffff;
  --surface-2: #efedea;
  --ink: #1b1a19;
  --ink-muted: #6b6862;
  --line: #ddd9d3;
  --accent: #2f6f62;
  --accent-ink: #ffffff;
  --danger: #b3261e;
  --ok: #2f6f3f;

  --radius: 10px;
  --gap-1: 4px;
  --gap-2: 8px;
  --gap-3: 16px;
  --gap-4: 24px;
  --gap-5: 40px;

  --font-sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --step--1: 0.875rem;
  --step-0: 1rem;
  --step-1: 1.25rem;
  --step-2: 1.5rem;
  --step-3: 2rem;

  --tap: 44px;   /* minimum touch target */
}
```

- [ ] **Step 3: Write the app shell into `base.html`**

```html
<!doctype html>
<html lang="hu">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#f7f6f4">
  <title>{% block title %}{{ S["app_name"] }}{% endblock %}</title>
  <link rel="manifest" href="/static/manifest.json">
  <link rel="stylesheet" href="/static/tokens.css">
  <link rel="stylesheet" href="/static/app.css">
  <script src="/static/htmx.min.js" defer></script>
</head>
<body class="{% block body_class %}{% endblock %}">
  {% if user %}
  <header class="topbar">
    <span class="topbar__title">{% block heading %}{% endblock %}</span>
    {% block topbar_actions %}{% endblock %}
  </header>
  {% endif %}

  <main class="content">{% block body %}{% endblock %}</main>

  {% if user %}
  <nav class="tabbar">
    <a href="/" class="tab {% if tab == 'today' %}is-active{% endif %}">{{ S["nav_today"] }}</a>
    <a href="/calendar" class="tab {% if tab == 'calendar' %}is-active{% endif %}">{{ S["nav_calendar"] }}</a>
    <a href="/clients" class="tab {% if tab == 'clients' %}is-active{% endif %}">{{ S["nav_clients"] }}</a>
    <a href="/settings" class="tab {% if tab == 'more' %}is-active{% endif %}">{{ S["nav_more"] }}</a>
  </nav>
  {% endif %}
</body>
</html>
```

Add a context processor so `user` and `tab` are always present. In
`app/main.py`, inside `lifespan`, after creating `templates`:

```python
    templates.env.globals["S"] = S            # from app.strings.hu import S
    app.state.templates = templates
```

and every route that renders passes `{"user": user, "tab": "<name>"}`.

- [ ] **Step 4: Write `static/app.css`**

```css
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }

body {
  background: var(--bg);
  color: var(--ink);
  font: var(--step-0)/1.5 var(--font-sans);
  padding-bottom: calc(var(--tap) + var(--gap-4));  /* room for the tabbar */
}

.topbar {
  position: sticky; top: 0; z-index: 10;
  display: flex; align-items: center; justify-content: space-between;
  gap: var(--gap-3);
  padding: var(--gap-3);
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.topbar__title { font-size: var(--step-1); font-weight: 600; }

.content { padding: var(--gap-3); max-width: 62rem; margin: 0 auto; }

.tabbar {
  position: fixed; inset: auto 0 0 0;
  display: grid; grid-template-columns: repeat(4, 1fr);
  background: var(--surface);
  border-top: 1px solid var(--line);
}
.tab {
  min-height: var(--tap);
  display: grid; place-items: center;
  color: var(--ink-muted); text-decoration: none;
  font-size: var(--step--1);
}
.tab.is-active { color: var(--accent); font-weight: 600; }

button, .button {
  min-height: var(--tap);
  padding: 0 var(--gap-3);
  border: 1px solid transparent;
  border-radius: var(--radius);
  background: var(--accent);
  color: var(--accent-ink);
  font: inherit; font-weight: 600;
  cursor: pointer;
}
button.secondary {
  background: var(--surface); color: var(--ink); border-color: var(--line);
}

input, select, textarea {
  min-height: var(--tap);
  width: 100%;
  padding: var(--gap-2) var(--gap-3);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--ink);
  font: inherit;
}
label { display: block; margin: var(--gap-3) 0 var(--gap-1); font-weight: 600; }

.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: var(--gap-3);
}

/* Red means one thing only: a client alert. */
.alert-dot {
  display: inline-block; width: 10px; height: 10px; border-radius: 50%;
  background: var(--danger);
}
.alert-banner {
  border-left: 4px solid var(--danger);
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
  padding: var(--gap-3);
  border-radius: var(--radius);
}

.error { color: var(--danger); }

.login { max-width: 22rem; margin: 15vh auto; padding: var(--gap-4); }

@media (min-width: 48rem) {
  .tabbar {
    position: sticky; top: 0; inset: 0 auto 0 0;
    width: 12rem; height: 100vh;
    grid-template-columns: 1fr; align-content: start;
    border-right: 1px solid var(--line); border-top: 0;
  }
  body { padding-bottom: 0; display: grid; grid-template-columns: 12rem 1fr; }
  .topbar, .content { grid-column: 2; }
}
```

- [ ] **Step 5: Write the screenshot script and run the loop**

Three settings here are load-bearing and have already cost a rejected redesign
once: the bundled Playwright browser is version-mismatched so `executablePath`
must be given, Chrome refuses to start as root without `--no-sandbox`, and a
fixed-height container makes `fullPage` stop at the fold, so set a tall
viewport instead.

```javascript
// scripts/shot.mjs
// usage: node scripts/shot.mjs http://localhost:8000/login out.png [width] [height]
import { chromium } from 'playwright-core';

const [, , url, out, w = '390', h = '1400'] = process.argv;
const browser = await chromium.launch({
  executablePath: '/usr/bin/google-chrome',
  args: ['--no-sandbox'],
});
const page = await browser.newPage({
  viewport: { width: Number(w), height: Number(h) },
  deviceScaleFactor: 2,
});
await page.goto(url, { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);   // an early capture catches mid-reflow
await page.screenshot({ path: out });
await browser.close();
```

Run the loop until the login screen looks deliberate rather than default:

```bash
node scripts/shot.mjs http://localhost:8000/login /tmp/login-390.png 390 900
node scripts/shot.mjs http://localhost:8000/login /tmp/login-1280.png 1280 900
```

Read both images. A diff review verifies correctness; only the image verifies
appearance. Iterate on `tokens.css` and `app.css`, not on the markup.

- [ ] **Step 6: Replace the ASCII placeholders in `strings/hu.py` with accented Hungarian**

`Bejelentkezes` becomes `Bejelentkezés`, `Felhasznalonev` becomes
`Felhasználónév`, and so on for every key. Re-run one screenshot afterwards to
confirm the chosen font renders the accents without clipping the line box.

- [ ] **Step 7: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): design tokens, app shell and the styled login screen"
```

---

### Task 4: Treatment catalogue

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/app/services/{__init__.py,treatments.py}`
- Create: `compose/proxmox-lxc-100/pedikur/app/routers/settings.py`
- Create: `compose/proxmox-lxc-100/pedikur/app/templates/settings_treatments.html`
- Modify: `compose/proxmox-lxc-100/pedikur/app/main.py` (include the router)
- Modify: `compose/proxmox-lxc-100/pedikur/app/strings/hu.py`

**Interfaces:**
- Consumes: `models.Treatment`, `security.require_user`, `db.Database.session()`.
- Produces: `treatments.list_active(session) -> list[Treatment]`,
  `treatments.list_all(session) -> list[Treatment]`,
  `treatments.create(session, name, duration_min, price_cents, created_by) -> Treatment`,
  `treatments.update(session, treatment_id, **fields) -> Treatment`,
  `treatments.deactivate(session, treatment_id) -> None`.
  Prices move as integer cents everywhere; the templates format them with the
  `eur` filter defined below.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_treatments.py
import pytest

from app import migrate
from app.db import Database
from app.services import treatments


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_create_and_list_active(db):
    with db.session() as s:
        treatments.create(s, "Pedikur", 45, 2500, created_by="1")
        gel = treatments.create(s, "Gellakk", 30, 1800, created_by="1")
        treatments.deactivate(s, gel.id)
    with db.session() as s:
        active = treatments.list_active(s)
        assert [t.name for t in active] == ["Pedikur"]
        assert len(treatments.list_all(s)) == 2


def test_price_is_stored_as_integer_cents(db):
    with db.session() as s:
        t = treatments.create(s, "Pedikur", 45, 2500, created_by="1")
        assert t.price_cents == 2500
        assert isinstance(t.price_cents, int)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_treatments.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 3: Write `app/services/treatments.py`**

```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Treatment


def list_active(session: Session) -> list[Treatment]:
    return list(session.scalars(
        select(Treatment).where(Treatment.active == 1).order_by(Treatment.name)))


def list_all(session: Session) -> list[Treatment]:
    return list(session.scalars(select(Treatment).order_by(Treatment.name)))


def create(session: Session, name: str, duration_min: int,
           price_cents: int, created_by: str) -> Treatment:
    treatment = Treatment(name=name.strip(), duration_min=int(duration_min),
                          price_cents=int(price_cents), active=1,
                          created_by=created_by)
    session.add(treatment)
    session.flush()
    return treatment


def update(session: Session, treatment_id: int, **fields) -> Treatment:
    treatment = session.get(Treatment, treatment_id)
    if treatment is None:
        raise LookupError(f"no treatment {treatment_id}")
    for key, value in fields.items():
        setattr(treatment, key, value)
    session.flush()
    return treatment


def deactivate(session: Session, treatment_id: int) -> None:
    """Treatments are never deleted: historical Visit Items point at them."""
    update(session, treatment_id, active=0)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_treatments.py -v`
Expected: PASS, 2 tests

- [ ] **Step 5: Add the `eur` template filter**

In `app/main.py`, inside `lifespan` next to the globals:

```python
    templates.env.filters["eur"] = lambda cents: f"{cents / 100:.2f} EUR".replace(".", ",")
```

- [ ] **Step 6: Write `app/routers/settings.py` and the template**

```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.services import treatments

router = APIRouter(prefix="/settings")


@router.get("")
def index(request: Request, user: User = Depends(security.require_user)):
    return RedirectResponse("/settings/treatments", status_code=303)


@router.get("/treatments")
def treatment_list(request: Request, user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = treatments.list_all(s)
        return request.app.state.templates.TemplateResponse(
            request, "settings_treatments.html",
            {"user": user, "tab": "more", "treatments": rows})


@router.post("/treatments")
def treatment_create(request: Request,
                     name: str = Form(...),
                     duration_min: int = Form(...),
                     price_eur: str = Form(...),
                     user: User = Depends(security.require_user)):
    cents = int(round(float(price_eur.replace(",", ".")) * 100))
    with request.app.state.db.session() as s:
        treatments.create(s, name, duration_min, cents, created_by=str(user.id))
    return RedirectResponse("/settings/treatments", status_code=303)


@router.post("/treatments/{treatment_id}/deactivate")
def treatment_deactivate(request: Request, treatment_id: int,
                         user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        treatments.deactivate(s, treatment_id)
    return RedirectResponse("/settings/treatments", status_code=303)
```

```html
<!-- templates/settings_treatments.html -->
{% extends "base.html" %}
{% block heading %}{{ S["treatments_title"] }}{% endblock %}
{% block body %}
<ul class="list">
  {% for t in treatments %}
  <li class="card {% if not t.active %}is-muted{% endif %}">
    <strong>{{ t.name }}</strong>
    <span>{{ t.duration_min }} {{ S["minutes_short"] }}</span>
    <span>{{ t.price_cents | eur }}</span>
    {% if t.active %}
    <form method="post" action="/settings/treatments/{{ t.id }}/deactivate">
      <button class="secondary" type="submit">{{ S["deactivate"] }}</button>
    </form>
    {% endif %}
  </li>
  {% endfor %}
</ul>

<form method="post" action="/settings/treatments" class="card">
  <label for="name">{{ S["treatment_name"] }}</label>
  <input id="name" name="name" required>
  <label for="duration_min">{{ S["treatment_duration"] }}</label>
  <input id="duration_min" name="duration_min" type="number" min="5" step="5"
         value="45" required>
  <label for="price_eur">{{ S["treatment_price"] }}</label>
  <input id="price_eur" name="price_eur" inputmode="decimal" required>
  <button type="submit">{{ S["save"] }}</button>
</form>
{% endblock %}
```

Add to `strings/hu.py`: `treatments_title` "Kezelések", `treatment_name`
"Név", `treatment_duration` "Hossz (perc)", `treatment_price` "Ár (EUR)",
`minutes_short` "perc", `deactivate` "Kivezetés", `save` "Mentés".

- [ ] **Step 7: Add the working hours screen to the same router**

Without this she cannot change her opening hours without SQL, and the seeded
Monday-to-Friday 09:00-17:00 will not match her actual week. The calendar grid
is bounded by these rows, so this is not a settings nicety.

```python
# append to app/routers/settings.py
from app.models import WorkingHours

WEEKDAYS = ["Hetfo", "Kedd", "Szerda", "Csutortok", "Pentek", "Szombat", "Vasarnap"]


@router.get("/hours")
def hours_form(request: Request, user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = {r.weekday: r for r in s.query(WorkingHours)
                .filter(WorkingHours.weekday.isnot(None))}
        return request.app.state.templates.TemplateResponse(
            request, "settings_hours.html",
            {"user": user, "tab": "more", "rows": rows,
             "weekdays": list(enumerate(WEEKDAYS))})


@router.post("/hours")
async def hours_save(request: Request,
                     user: User = Depends(security.require_user)):
    form = await request.form()
    with request.app.state.db.session() as s:
        for weekday in range(7):
            closed = form.get(f"closed_{weekday}") is not None
            start = form.get(f"start_{weekday}") or "09:00"
            end = form.get(f"end_{weekday}") or "17:00"
            row = s.query(WorkingHours).filter_by(weekday=weekday).one_or_none()
            if row is None:
                row = WorkingHours(weekday=weekday, start=start, end=end,
                                   is_closed=int(closed))
                s.add(row)
            else:
                row.start, row.end, row.is_closed = start, end, int(closed)
    return RedirectResponse("/settings/hours", status_code=303)
```

```html
<!-- templates/settings_hours.html -->
{% extends "base.html" %}
{% block heading %}{{ S["hours_title"] }}{% endblock %}
{% block body %}
<form method="post" action="/settings/hours" class="card">
  {% for weekday, label in weekdays %}
  {% set row = rows.get(weekday) %}
  <fieldset>
    <legend>{{ label }}</legend>
    <label class="check">
      <input type="checkbox" name="closed_{{ weekday }}"
             {% if row is none or row.is_closed %}checked{% endif %}>
      {{ S["closed"] }}
    </label>
    <input type="time" name="start_{{ weekday }}"
           value="{{ row.start if row else '09:00' }}">
    <input type="time" name="end_{{ weekday }}"
           value="{{ row.end if row else '17:00' }}">
  </fieldset>
  {% endfor %}
  <button type="submit">{{ S["save"] }}</button>
</form>
{% endblock %}
```

`<input type="time">` is native; no picker library. Add to `strings/hu.py`:
`hours_title` "Munkaido", `closed` "Zarva". Add a link to `/settings/hours`
and `/settings/treatments` from the Settings index instead of the current
redirect.

An unchecked day writes an open row; a checked one writes `is_closed = 1`. The
date-level overrides in `working_hours` (holidays, a single closed afternoon)
have no screen in phase 1 and are entered by hand until phase 3 needs them.

- [ ] **Step 8: Screenshot both settings screens and adjust `app.css` only**

```bash
node scripts/shot.mjs http://localhost:8000/settings/treatments /tmp/tr.png 390 1200
node scripts/shot.mjs http://localhost:8000/settings/hours /tmp/hours.png 390 1200
```

Add the `.list` and `.is-muted` rules to `app.css` based on what the image
shows. Do not introduce new colours; use the Task 3 tokens.

- [ ] **Step 9: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): treatment catalogue and working hours settings"
```

---

### Task 5: Clients, search and the client card

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/app/services/clients.py`
- Create: `compose/proxmox-lxc-100/pedikur/app/routers/clients.py`
- Create: `compose/proxmox-lxc-100/pedikur/app/templates/{clients.html,client.html}`
- Create: `compose/proxmox-lxc-100/pedikur/app/templates/partials/client_search.html`
- Test: `compose/proxmox-lxc-100/pedikur/tests/test_clients.py`

**Interfaces:**
- Produces: `clients.search(session, query: str, limit: int = 20) -> list[Client]`,
  `clients.get(session, client_id) -> Client | None`,
  `clients.create(session, name, phone, created_by, **optional) -> Client`,
  `clients.update(session, client_id, **fields) -> Client`,
  `clients.archive(session, client_id) -> None`,
  `clients.history(session, client_id) -> list[Visit]` (newest first, `done` only).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_clients.py
import pytest

from app import migrate
from app.db import Database
from app.services import clients


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_search_is_case_insensitive_and_partial(db):
    with db.session() as s:
        clients.create(s, "Kovacs Anna", "0900111222", created_by="1")
        clients.create(s, "Nagy Bela", None, created_by="1")
    with db.session() as s:
        assert [c.name for c in clients.search(s, "kovacs")] == ["Kovacs Anna"]
        assert [c.name for c in clients.search(s, "an")] == ["Kovacs Anna"]
        assert clients.search(s, "zzz") == []


def test_archived_clients_are_hidden_from_search(db):
    with db.session() as s:
        c = clients.create(s, "Kovacs Anna", None, created_by="1")
        clients.archive(s, c.id)
    with db.session() as s:
        assert clients.search(s, "kovacs") == []
        assert clients.get(s, c.id) is not None   # still reachable by id


def test_alert_is_stored_but_never_returned_by_search_projection(db):
    with db.session() as s:
        c = clients.create(s, "Kovacs Anna", None, created_by="1",
                           alert="cukorbeteg")
    with db.session() as s:
        found = clients.search(s, "kovacs")[0]
        assert found.has_alert is True
        # the wording must not leave the service: a list screen never shows it
        assert not hasattr(found, "alert")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_clients.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.clients'`

- [ ] **Step 3: Write `app/services/clients.py`**

```python
"""Client queries.

Search returns a projection, not the model: the alert TEXT must never travel
to a list screen, only the fact that one exists. The Today and Clients screens
show a red dot; the wording lives inside the card.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Client, Visit


@dataclass(frozen=True)
class ClientRow:
    id: int
    name: str
    phone: str | None
    has_alert: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def search(session: Session, query: str, limit: int = 20) -> list[ClientRow]:
    stmt = select(Client).where(Client.archived_at.is_(None))
    if query.strip():
        stmt = stmt.where(Client.name.ilike(f"%{query.strip()}%"))
    stmt = stmt.order_by(Client.name).limit(limit)
    return [
        ClientRow(id=c.id, name=c.name, phone=c.phone,
                  has_alert=bool(c.alert and c.alert.strip()))
        for c in session.scalars(stmt)
    ]


def get(session: Session, client_id: int) -> Client | None:
    return session.get(Client, client_id)


def create(session: Session, name: str, phone: str | None,
           created_by: str, **optional) -> Client:
    client = Client(name=name.strip(), phone=phone, created_by=created_by,
                    created_at=_now(), **optional)
    session.add(client)
    session.flush()
    return client


def update(session: Session, client_id: int, **fields) -> Client:
    client = session.get(Client, client_id)
    if client is None:
        raise LookupError(f"no client {client_id}")
    for key, value in fields.items():
        setattr(client, key, value)
    session.flush()
    return client


def archive(session: Session, client_id: int) -> None:
    """Removed from the working lists, every record kept. Reversible.
    This is not Erase: Erase empties the identifying and health fields and is
    admin only, and arrives with the GDPR work in a later phase."""
    update(session, client_id, archived_at=_now())


def history(session: Session, client_id: int) -> list[Visit]:
    stmt = (select(Visit)
            .where(Visit.client_id == client_id,
                   Visit.status == "done",
                   Visit.deleted_at.is_(None))
            .order_by(Visit.starts_at.desc()))
    return list(session.scalars(stmt))
```

- [ ] **Step 4: Run it to verify it passes**

Run: `python -m pytest tests/test_clients.py -v`
Expected: PASS, 3 tests

- [ ] **Step 5: Write `app/routers/clients.py`**

```python
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.services import clients

router = APIRouter(prefix="/clients")


@router.get("")
def index(request: Request, q: str = "",
          user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = clients.search(s, q)
    return request.app.state.templates.TemplateResponse(
        request, "clients.html",
        {"user": user, "tab": "clients", "rows": rows, "q": q})


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
    with request.app.state.db.session() as s:
        client = clients.create(s, name, phone or None, created_by=str(user.id))
        client_id = client.id
    return RedirectResponse(f"/clients/{client_id}", status_code=303)


@router.get("/{client_id}")
def card(request: Request, client_id: int,
         user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        client = clients.get(s, client_id)
        if client is None:
            return RedirectResponse("/clients", status_code=303)
        visits = clients.history(s, client_id)
        return request.app.state.templates.TemplateResponse(
            request, "client.html",
            {"user": user, "tab": "clients", "client": client, "visits": visits})


@router.post("/{client_id}")
def edit(request: Request, client_id: int,
         name: str = Form(...), phone: str = Form(""),
         email: str = Form(""), address: str = Form(""),
         alert: str = Form(""), notes: str = Form(""),
         user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        clients.update(s, client_id, name=name, phone=phone or None,
                       email=email or None, address=address or None,
                       alert=alert or None, notes=notes or None)
    return RedirectResponse(f"/clients/{client_id}", status_code=303)
```

- [ ] **Step 6: Write the templates**

```html
<!-- templates/clients.html -->
{% extends "base.html" %}
{% block heading %}{{ S["nav_clients"] }}{% endblock %}
{% block body %}
<input type="search" name="q" value="{{ q }}" placeholder="{{ S['search'] }}"
       hx-get="/clients/search" hx-trigger="input changed delay:200ms, load"
       hx-target="#results" autocomplete="off">
<div id="results">{% include "partials/client_search.html" %}</div>

<details class="card">
  <summary>{{ S["new_client"] }}</summary>
  <form method="post" action="/clients">
    <label for="name">{{ S["client_name"] }}</label>
    <input id="name" name="name" required>
    <label for="phone">{{ S["client_phone"] }}</label>
    <input id="phone" name="phone" type="tel" inputmode="tel">
    <button type="submit">{{ S["save"] }}</button>
  </form>
</details>
{% endblock %}
```

```html
<!-- templates/partials/client_search.html -->
<ul class="list">
  {% for row in rows %}
  <li>
    <a class="card row" href="/clients/{{ row.id }}">
      {% if row.has_alert %}<span class="alert-dot" aria-label="{{ S['has_alert'] }}"></span>{% endif %}
      <strong>{{ row.name }}</strong>
      {% if row.phone %}<span class="muted">{{ row.phone }}</span>{% endif %}
    </a>
  </li>
  {% else %}
  <li class="muted">{{ S["no_results"] }}</li>
  {% endfor %}
</ul>
```

```html
<!-- templates/client.html -->
{% extends "base.html" %}
{% block heading %}{{ client.name }}{% endblock %}
{% block body %}
{% if client.alert %}
<p class="alert-banner"><strong>{{ S["alert_label"] }}:</strong> {{ client.alert }}</p>
{% endif %}

<form method="post" action="/clients/{{ client.id }}" class="card">
  <label for="name">{{ S["client_name"] }}</label>
  <input id="name" name="name" value="{{ client.name }}" required>
  <label for="phone">{{ S["client_phone"] }}</label>
  <input id="phone" name="phone" type="tel" value="{{ client.phone or '' }}">
  <label for="email">{{ S["client_email"] }}</label>
  <input id="email" name="email" type="email" value="{{ client.email or '' }}">
  <label for="address">{{ S["client_address"] }}</label>
  <input id="address" name="address" value="{{ client.address or '' }}">
  <label for="alert">{{ S["alert_label"] }}</label>
  <input id="alert" name="alert" value="{{ client.alert or '' }}"
         placeholder="{{ S['alert_hint'] }}">
  <label for="notes">{{ S["client_notes"] }}</label>
  <textarea id="notes" name="notes" rows="3">{{ client.notes or '' }}</textarea>
  <button type="submit">{{ S["save"] }}</button>
</form>

<h2>{{ S["history"] }}</h2>
<ul class="list">
  {% for v in visits %}
  <li class="card">
    <strong>{{ v.starts_at | localdate }}</strong>
    {% for item in v.items if item.kind == 'treatment' %}
      <span>{{ item.treatment.name }}</span>
    {% endfor %}
    {% if v.findings %}<p class="muted">{{ v.findings }}</p>{% endif %}
  </li>
  {% else %}
  <li class="muted">{{ S["no_history"] }}</li>
  {% endfor %}
</ul>
{% endblock %}
```

`localdate` is added in Task 6 with the rest of the time handling. Until then
the history list is empty, so the filter is not yet reached.

Add to `strings/hu.py`: `search` "Keresés", `new_client` "Új kliens",
`client_name` "Név", `client_phone` "Telefon", `client_email` "E-mail",
`client_address` "Cím", `client_notes` "Megjegyzés", `alert_label`
"Figyelmeztetés", `alert_hint` "cukorbetegség, véralvadásgátló, allergia",
`has_alert` "Figyelmeztetés", `history` "Előzmény", `no_history`
"Még nincs lezárt látogatás", `no_results` "Nincs találat".

- [ ] **Step 7: Screenshot both screens and adjust `app.css`**

```bash
node scripts/shot.mjs http://localhost:8000/clients /tmp/clients.png 390 1200
node scripts/shot.mjs http://localhost:8000/clients/1 /tmp/client.png 390 1600
```

Check specifically that the red dot reads as a warning at arm's length and that
no alert text appears on the list screen.

- [ ] **Step 8: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): clients, search projection and the client card"
```

---

### Task 6: Visits - time handling, booking rules and the booking form

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/app/services/{timeutil.py,visits.py}`
- Create: `compose/proxmox-lxc-100/pedikur/app/routers/visits.py`
- Create: `compose/proxmox-lxc-100/pedikur/app/templates/visit_form.html`
- Test: `compose/proxmox-lxc-100/pedikur/tests/test_visits.py`

**Interfaces:**
- Produces: `timeutil.LOCAL` (`ZoneInfo`), `timeutil.to_utc_iso(datetime) -> str`,
  `timeutil.from_utc_iso(str) -> datetime` (aware, local), `timeutil.local_now() -> datetime`,
  and the Jinja filters `localdate`, `localtime`.
  `visits.SlotTaken` (exception), `visits.book(session, client_id, starts_at_local, treatment_ids, created_by, ends_at_local=None) -> Visit`,
  `visits.reschedule(session, visit_id, starts_at_local, ends_at_local) -> Visit`,
  `visits.add_treatment(session, visit_id, treatment_id) -> Visit`,
  `visits.set_status(session, visit_id, status) -> Visit`,
  `visits.overlapping(session, start_utc, end_utc, exclude_id=None) -> list[Visit]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visits.py
from datetime import datetime, timedelta

import pytest

from app import migrate
from app.db import Database
from app.services import clients, timeutil, treatments, visits


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


@pytest.fixture
def fixtures(db):
    with db.session() as s:
        client = clients.create(s, "Kovacs Anna", None, created_by="1")
        ped = treatments.create(s, "Pedikur", 45, 2500, created_by="1")
        gel = treatments.create(s, "Gellakk", 30, 1800, created_by="1")
        return {"client_id": client.id, "ped": ped.id, "gel": gel.id}


def _local(y, m, d, hh, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timeutil.LOCAL)


def test_utc_conversion_survives_the_dst_change(db):
    # Europe/Bratislava springs forward on 2027-03-28.
    before = timeutil.to_utc_iso(_local(2027, 3, 27, 9))
    after = timeutil.to_utc_iso(_local(2027, 3, 28, 9))
    assert before.startswith("2027-03-27T08:00")   # CET, UTC+1
    assert after.startswith("2027-03-28T07:00")    # CEST, UTC+2
    # and back again
    assert timeutil.from_utc_iso(after).hour == 9


def test_ends_at_is_the_summed_duration(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"], fixtures["gel"]], created_by="1")
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 11, 15)


def test_manual_ends_at_wins_and_is_not_shrunk_by_a_new_treatment(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1",
                            ends_at_local=_local(2026, 9, 10, 12))
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 12)
        visits.add_treatment(s, visit.id, fixtures["gel"])
        # 45 + 30 = 75 minutes fits inside the manual window, so it stays
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 12)


def test_ends_at_grows_when_the_sum_exceeds_it(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.add_treatment(s, visit.id, fixtures["gel"])
        assert timeutil.from_utc_iso(visit.ends_at) == _local(2026, 9, 10, 11, 15)


def test_overlapping_booking_is_refused(db, fixtures):
    with db.session() as s:
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                    [fixtures["ped"]], created_by="1")
    with db.session() as s:
        with pytest.raises(visits.SlotTaken):
            visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10, 30),
                        [fixtures["gel"]], created_by="1")


def test_a_cancelled_visit_frees_its_slot(db, fixtures):
    with db.session() as s:
        first = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        visits.set_status(s, first.id, "cancelled")
    with db.session() as s:
        visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                    [fixtures["gel"]], created_by="1")   # must not raise
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_visits.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.timeutil'`

- [ ] **Step 3: Write `app/services/timeutil.py`**

```python
"""Instants are stored UTC and rendered local. Working hours are wall clock
and never pass through here: converting 09:00 would move opening time twice a
year in the wrong direction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo("Europe/Bratislava")


def local_now() -> datetime:
    return datetime.now(LOCAL)


def to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL)
    return value.astimezone(timezone.utc).isoformat()


def from_utc_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL)


def localdate(value: str) -> str:
    return from_utc_iso(value).strftime("%Y-%m-%d")


def localtime(value: str) -> str:
    return from_utc_iso(value).strftime("%H:%M")
```

Register the two filters in `app/main.py` beside the `eur` filter:

```python
    templates.env.filters["localdate"] = timeutil.localdate
    templates.env.filters["localtime"] = timeutil.localtime
```

- [ ] **Step 4: Write `app/services/visits.py`**

```python
"""Booking and the Visit lifecycle.

A Visit is one client session, booked ahead or walked in. Booking and
treatment record are the same row at different points in its life, which is
why there is no separate visit table: two rows a day apart would contribute a
zero-day gap to the Visit Interval median and, after a few of those, mark
everyone permanently overdue.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Treatment, Visit, VisitItem
from app.services import timeutil

ACTIVE_STATUSES = ("planned", "done")


class SlotTaken(Exception):
    """Another Visit already occupies the requested window."""


def overlapping(session: Session, start_utc: str, end_utc: str,
                exclude_id: int | None = None) -> list[Visit]:
    stmt = (select(Visit)
            .where(Visit.status.in_(ACTIVE_STATUSES),
                   Visit.deleted_at.is_(None),
                   Visit.starts_at < end_utc,
                   Visit.ends_at > start_utc))
    if exclude_id is not None:
        stmt = stmt.where(Visit.id != exclude_id)
    return list(session.scalars(stmt))


def _treatments(session: Session, treatment_ids: list[int]) -> list[Treatment]:
    found = {t.id: t for t in session.scalars(
        select(Treatment).where(Treatment.id.in_(treatment_ids)))}
    missing = [i for i in treatment_ids if i not in found]
    if missing:
        raise LookupError(f"unknown treatment ids: {missing}")
    return [found[i] for i in treatment_ids]


def book(session: Session, client_id: int, starts_at_local: datetime,
         treatment_ids: list[int], created_by: str,
         ends_at_local: datetime | None = None) -> Visit:
    """Create a planned Visit.

    ends_at defaults to the summed duration of the treatments and may be
    widened by hand. The overlap check runs inside this transaction: checking
    first and inserting after is a race even with two users and two tabs.
    """
    if not treatment_ids:
        raise ValueError("a Visit needs at least one Treatment")
    chosen = _treatments(session, treatment_ids)
    total_min = sum(t.duration_min for t in chosen)
    computed_end = starts_at_local + timedelta(minutes=total_min)
    end_local = max(ends_at_local, computed_end) if ends_at_local else computed_end

    start_utc = timeutil.to_utc_iso(starts_at_local)
    end_utc = timeutil.to_utc_iso(end_local)
    if overlapping(session, start_utc, end_utc):
        raise SlotTaken(f"{start_utc} .. {end_utc}")

    visit = Visit(client_id=client_id, starts_at=start_utc, ends_at=end_utc,
                  status="planned", created_by=created_by,
                  created_at=timeutil.to_utc_iso(timeutil.local_now()))
    session.add(visit)
    session.flush()
    for treatment in chosen:
        session.add(VisitItem(visit_id=visit.id, kind="treatment",
                              treatment_id=treatment.id, qty=1,
                              unit_price_cents=treatment.price_cents))
    session.flush()
    return visit


def add_treatment(session: Session, visit_id: int, treatment_id: int) -> Visit:
    """Add a Treatment to an existing Visit.

    ends_at only ever grows: if she widened the window by hand, adding a
    treatment must not shrink it back behind her.
    """
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    treatment = session.get(Treatment, treatment_id)
    if treatment is None:
        raise LookupError(f"no treatment {treatment_id}")

    session.add(VisitItem(visit_id=visit.id, kind="treatment",
                          treatment_id=treatment.id, qty=1,
                          unit_price_cents=treatment.price_cents))
    session.flush()

    total_min = sum(i.treatment.duration_min for i in visit.items
                    if i.kind == "treatment" and i.treatment is not None)
    needed_end = timeutil.from_utc_iso(visit.starts_at) + timedelta(minutes=total_min)
    if needed_end > timeutil.from_utc_iso(visit.ends_at):
        visit.ends_at = timeutil.to_utc_iso(needed_end)
    session.flush()
    return visit


def reschedule(session: Session, visit_id: int, starts_at_local: datetime,
               ends_at_local: datetime) -> Visit:
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    start_utc = timeutil.to_utc_iso(starts_at_local)
    end_utc = timeutil.to_utc_iso(ends_at_local)
    if overlapping(session, start_utc, end_utc, exclude_id=visit_id):
        raise SlotTaken(f"{start_utc} .. {end_utc}")
    visit.starts_at, visit.ends_at = start_utc, end_utc
    session.flush()
    return visit


def set_status(session: Session, visit_id: int, status: str) -> Visit:
    if status not in ("planned", "done", "cancelled", "no_show"):
        raise ValueError(f"bad status: {status}")
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    visit.status = status
    session.flush()
    return visit


def unclosed(session: Session) -> list[Visit]:
    """Visits whose window has passed but were never closed.

    They are never closed automatically. Auto-closing would invent revenue
    from a client who may not have come; auto-marking no_show would invent the
    opposite. It also matters beyond the money: the Visit Interval counts only
    done Visits, so an unclosed one makes a client look as if they never came
    and puts them on the Recall List weeks early.
    """
    now_utc = timeutil.to_utc_iso(timeutil.local_now())
    stmt = (select(Visit)
            .where(Visit.status == "planned",
                   Visit.deleted_at.is_(None),
                   Visit.ends_at < now_utc)
            .order_by(Visit.starts_at))
    return list(session.scalars(stmt))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_visits.py -v`
Expected: PASS, 6 tests

- [ ] **Step 6: Write `app/routers/visits.py` and `templates/visit_form.html`**

```python
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.services import clients, timeutil, treatments, visits

router = APIRouter(prefix="/visits")


@router.get("/new")
def new(request: Request, start: str = "", client_id: int | None = None,
        user: User = Depends(security.require_user)):
    """`start` is a local ISO datetime, e.g. 2026-09-10T10:00, from the grid."""
    with request.app.state.db.session() as s:
        return request.app.state.templates.TemplateResponse(
            request, "visit_form.html",
            {"user": user, "tab": "calendar", "visit": None, "start": start,
             "client_id": client_id, "treatments": treatments.list_active(s),
             "clients": clients.search(s, ""), "error": None})


@router.post("/new")
def create(request: Request,
           client_id: int = Form(...),
           start: str = Form(...),
           end: str = Form(""),
           treatment_ids: list[int] = Form(...),
           user: User = Depends(security.require_user)):
    starts = datetime.fromisoformat(start).replace(tzinfo=timeutil.LOCAL)
    ends = (datetime.fromisoformat(end).replace(tzinfo=timeutil.LOCAL)
            if end else None)
    with request.app.state.db.session() as s:
        try:
            visits.book(s, client_id, starts, treatment_ids,
                        created_by=str(user.id), ends_at_local=ends)
        except visits.SlotTaken:
            return request.app.state.templates.TemplateResponse(
                request, "visit_form.html",
                {"user": user, "tab": "calendar", "visit": None, "start": start,
                 "client_id": client_id, "treatments": treatments.list_active(s),
                 "clients": clients.search(s, ""),
                 "error": request.app.state.templates.env.globals["S"]["slot_taken"]},
                status_code=409)
    return RedirectResponse(f"/calendar?day={starts.date()}", status_code=303)
```

```html
<!-- templates/visit_form.html -->
{% extends "base.html" %}
{% block heading %}{{ S["new_visit"] }}{% endblock %}
{% block body %}
{% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}
<form method="post" action="/visits/new" class="card">
  <label for="client_id">{{ S["client"] }}</label>
  <select id="client_id" name="client_id" required>
    {% for c in clients %}
    <option value="{{ c.id }}" {% if c.id == client_id %}selected{% endif %}>
      {{ c.name }}{% if c.phone %} - {{ c.phone }}{% endif %}
    </option>
    {% endfor %}
  </select>

  <label>{{ S["treatments_title"] }}</label>
  {% for t in treatments %}
  <label class="check">
    <input type="checkbox" name="treatment_ids" value="{{ t.id }}">
    {{ t.name }} - {{ t.duration_min }} {{ S["minutes_short"] }} -
    {{ t.price_cents | eur }}
  </label>
  {% endfor %}

  <label for="start">{{ S["starts_at"] }}</label>
  <input id="start" name="start" type="datetime-local" value="{{ start }}" required>

  <label for="end">{{ S["ends_at_optional"] }}</label>
  <input id="end" name="end" type="datetime-local">

  <button type="submit">{{ S["save"] }}</button>
</form>
{% endblock %}
```

`<input type="datetime-local">` is the native control: no picker library.

Add to `strings/hu.py`: `new_visit` "Új időpont", `client` "Kliens",
`starts_at` "Kezdés", `ends_at_optional` "Vége (ha hosszabb a szokásosnál)",
`slot_taken` "Ez az idősáv már foglalt.".

- [ ] **Step 7: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): visit booking, UTC storage and the growing ends_at rule"
```

---

### Task 7: The week calendar

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/app/services/schedule.py`
- Create: `compose/proxmox-lxc-100/pedikur/app/routers/calendar.py`
- Create: `compose/proxmox-lxc-100/pedikur/app/templates/week.html`
- Test: `compose/proxmox-lxc-100/pedikur/tests/test_schedule.py`

**Interfaces:**
- Produces: `schedule.SLOT_MIN = 15`, `schedule.hours_for(session, day) -> DayHours | None`,
  `schedule.week_grid(session, monday) -> WeekGrid` where
  `WeekGrid(start_min: int, end_min: int, rows: int, days: list[DayColumn])`,
  `DayColumn(date, is_closed, open_min, close_min, blocks: list[VisitBlock])`,
  `VisitBlock(visit_id, client_name, has_alert, label, status, row_start, row_span)`.
  Row numbers are 1-based so they drop straight into `grid-row`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schedule.py
from datetime import date, datetime

import pytest

from app import migrate
from app.db import Database
from app.services import clients, schedule, timeutil, treatments, visits


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_seeded_week_is_open_monday_to_friday(db):
    with db.session() as s:
        assert schedule.hours_for(s, date(2026, 9, 7)).is_closed is False   # Mon
        assert schedule.hours_for(s, date(2026, 9, 12)) is None             # Sat


def test_date_override_beats_the_weekday_default(db):
    from app.models import WorkingHours
    with db.session() as s:
        s.add(WorkingHours(date="2026-09-09", start="00:00", end="00:00",
                           is_closed=1))
    with db.session() as s:
        assert schedule.hours_for(s, date(2026, 9, 9)).is_closed is True


def test_visit_lands_on_the_right_grid_rows(db):
    with db.session() as s:
        client = clients.create(s, "Kovacs Anna", None, created_by="1")
        ped = treatments.create(s, "Pedikur", 45, 2500, created_by="1")
        visits.book(s, client.id,
                    datetime(2026, 9, 7, 10, 0, tzinfo=timeutil.LOCAL),
                    [ped.id], created_by="1")
    with db.session() as s:
        grid = schedule.week_grid(s, date(2026, 9, 7))
        monday = grid.days[0]
        assert grid.start_min == 9 * 60          # seeded 09:00
        assert len(monday.blocks) == 1
        block = monday.blocks[0]
        assert block.row_start == 5              # 10:00 is four 15-min slots in
        assert block.row_span == 3               # 45 minutes
        assert block.client_name == "Kovacs Anna"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_schedule.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.schedule'`

- [ ] **Step 3: Write `app/services/schedule.py`**

```python
"""Working hours to a renderable week grid.

Phase 1 renders her own Visits only. Google busy blocks, buffers and free-slot
highlighting arrive in phase 3 and extend this module rather than replacing it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Visit, WorkingHours
from app.services import timeutil

SLOT_MIN = 15


@dataclass(frozen=True)
class DayHours:
    open_min: int
    close_min: int
    is_closed: bool


@dataclass(frozen=True)
class VisitBlock:
    visit_id: int
    client_name: str
    has_alert: bool
    label: str
    status: str
    row_start: int
    row_span: int


@dataclass(frozen=True)
class DayColumn:
    date: date
    is_closed: bool
    open_min: int
    close_min: int
    blocks: list[VisitBlock]


@dataclass(frozen=True)
class WeekGrid:
    monday: date
    start_min: int
    end_min: int
    rows: int
    days: list[DayColumn]


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def hours_for(session: Session, day: date) -> DayHours | None:
    """A date row overrides the weekday default. None means no hours at all."""
    row = session.scalars(
        select(WorkingHours).where(WorkingHours.date == day.isoformat())
    ).one_or_none()
    if row is None:
        row = session.scalars(
            select(WorkingHours).where(WorkingHours.weekday == day.weekday())
        ).one_or_none()
    if row is None:
        return None
    return DayHours(open_min=_to_minutes(row.start),
                    close_min=_to_minutes(row.end),
                    is_closed=bool(row.is_closed))


def week_grid(session: Session, monday: date) -> WeekGrid:
    days_dates = [monday + timedelta(days=i) for i in range(7)]
    hours = {d: hours_for(session, d) for d in days_dates}

    open_days = [h for h in hours.values() if h and not h.is_closed]
    start_min = min((h.open_min for h in open_days), default=8 * 60)
    end_min = max((h.close_min for h in open_days), default=18 * 60)
    rows = max(1, (end_min - start_min) // SLOT_MIN)

    window_start = datetime.combine(monday, datetime.min.time(),
                                    tzinfo=timeutil.LOCAL)
    window_end = window_start + timedelta(days=7)
    stmt = (select(Visit)
            .where(Visit.deleted_at.is_(None),
                   Visit.status.in_(("planned", "done")),
                   Visit.starts_at >= timeutil.to_utc_iso(window_start),
                   Visit.starts_at < timeutil.to_utc_iso(window_end))
            .order_by(Visit.starts_at))

    by_day: dict[date, list[VisitBlock]] = {d: [] for d in days_dates}
    for visit in session.scalars(stmt):
        local_start = timeutil.from_utc_iso(visit.starts_at)
        local_end = timeutil.from_utc_iso(visit.ends_at)
        day = local_start.date()
        if day not in by_day:
            continue
        start_offset = local_start.hour * 60 + local_start.minute - start_min
        duration = int((local_end - local_start).total_seconds() // 60)
        row_start = max(1, start_offset // SLOT_MIN + 1)
        row_span = max(1, math.ceil(duration / SLOT_MIN))
        names = [i.treatment.name for i in visit.items
                 if i.kind == "treatment" and i.treatment is not None]
        by_day[day].append(VisitBlock(
            visit_id=visit.id,
            client_name=visit.client.name,
            has_alert=bool(visit.client.alert and visit.client.alert.strip()),
            label=", ".join(names),
            status=visit.status,
            row_start=row_start,
            row_span=row_span,
        ))

    columns = []
    for d in days_dates:
        h = hours[d]
        columns.append(DayColumn(
            date=d,
            is_closed=h is None or h.is_closed,
            open_min=h.open_min if h else start_min,
            close_min=h.close_min if h else end_min,
            blocks=by_day[d],
        ))
    return WeekGrid(monday=monday, start_min=start_min, end_min=end_min,
                    rows=rows, days=columns)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_schedule.py -v`
Expected: PASS, 3 tests

- [ ] **Step 5: Write `app/routers/calendar.py`**

```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request

from app import security
from app.models import User
from app.services import schedule, timeutil

router = APIRouter(prefix="/calendar")


@router.get("")
def week(request: Request, day: str = "",
         user: User = Depends(security.require_user)):
    anchor = date.fromisoformat(day) if day else timeutil.local_now().date()
    monday = anchor - timedelta(days=anchor.weekday())
    with request.app.state.db.session() as s:
        grid = schedule.week_grid(s, monday)
    return request.app.state.templates.TemplateResponse(
        request, "week.html",
        {"user": user, "tab": "calendar", "grid": grid,
         "prev": (monday - timedelta(days=7)).isoformat(),
         "next": (monday + timedelta(days=7)).isoformat(),
         "today": timeutil.local_now().date(),
         "slot_min": schedule.SLOT_MIN})
```

- [ ] **Step 6: Write `templates/week.html`**

```html
{% extends "base.html" %}
{% block heading %}{{ grid.monday.strftime("%Y. %m. %d.") }}{% endblock %}
{% block topbar_actions %}
  <a class="button secondary" href="/calendar?day={{ prev }}">&larr;</a>
  <a class="button secondary" href="/calendar?day={{ next }}">&rarr;</a>
{% endblock %}
{% block body %}
<div class="week" style="--rows: {{ grid.rows }}">
  <div class="week__times">
    {% for row in range(grid.rows) %}
      {% set minute = grid.start_min + row * slot_min %}
      {% if minute % 60 == 0 %}
      <span class="week__time" style="grid-row: {{ row + 1 }}">
        {{ "%02d:00" | format(minute // 60) }}
      </span>
      {% endif %}
    {% endfor %}
  </div>

  {% for day in grid.days %}
  <div class="week__day {% if day.is_closed %}is-closed{% endif %}
              {% if day.date == today %}is-today{% endif %}">
    <div class="week__dayhead">{{ day.date.strftime("%a %d") }}</div>
    <div class="week__slots">
      {% for row in range(grid.rows) %}
        {% set minute = grid.start_min + row * slot_min %}
        {% if not day.is_closed and minute >= day.open_min and minute < day.close_min %}
        <a class="week__slot" style="grid-row: {{ row + 1 }}"
           href="/visits/new?start={{ day.date }}T{{ '%02d:%02d' | format(minute // 60, minute % 60) }}"
           aria-label="{{ S['book_here'] }}"></a>
        {% endif %}
      {% endfor %}

      {% for block in day.blocks %}
      <a class="week__visit is-{{ block.status }}"
         style="grid-row: {{ block.row_start }} / span {{ block.row_span }}"
         href="/visits/{{ block.visit_id }}/close">
        {% if block.has_alert %}<span class="alert-dot"></span>{% endif %}
        <strong>{{ block.client_name }}</strong>
        <span class="muted">{{ block.label }}</span>
      </a>
      {% endfor %}
    </div>
  </div>
  {% endfor %}
</div>
{% endblock %}
```

Add the grid CSS to `app.css`:

```css
.week {
  display: grid;
  grid-template-columns: 3.5rem repeat(7, minmax(6rem, 1fr));
  gap: var(--gap-1);
  overflow-x: auto;
}
.week__times, .week__slots {
  display: grid;
  grid-template-rows: repeat(var(--rows), 1.25rem);
}
.week__time { font-size: var(--step--1); color: var(--ink-muted); }
.week__dayhead {
  position: sticky; top: 0;
  padding: var(--gap-1); text-align: center; font-weight: 600;
  background: var(--surface); border-bottom: 1px solid var(--line);
}
.week__slots { position: relative; background: var(--surface); }
.week__slot { border-top: 1px solid var(--surface-2); }
.week__slot:hover { background: var(--surface-2); }
.week__day.is-closed .week__slots { background: var(--surface-2); }
.week__day.is-today .week__dayhead { color: var(--accent); }
.week__visit {
  grid-column: 1;
  margin: 1px;
  padding: var(--gap-1) var(--gap-2);
  border-radius: calc(var(--radius) / 2);
  background: var(--accent); color: var(--accent-ink);
  font-size: var(--step--1); text-decoration: none; overflow: hidden;
}
.week__visit.is-done { background: var(--ok); }
```

Add to `strings/hu.py`: `book_here` "Foglalás ide".

- [ ] **Step 7: Screenshot at both sizes and iterate**

```bash
node scripts/shot.mjs http://localhost:8000/calendar /tmp/week-1280.png 1280 1000
node scripts/shot.mjs http://localhost:8000/calendar /tmp/week-390.png 390 1200
```

On the phone the grid scrolls horizontally; check that a day column is still
wide enough to read a client name, and that the alert dot survives the
narrowest column.

- [ ] **Step 8: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): week calendar grid with click-to-book slots"
```

---

### Task 8: Closing a Visit in one tap

The single most important screen in phase 1. If closing a Visit takes longer
than about fifteen seconds she will stop doing it, and everything downstream -
revenue, the Visit Interval, the Recall List - is built on it happening.

**Files:**
- Modify: `compose/proxmox-lxc-100/pedikur/app/services/visits.py`
- Modify: `compose/proxmox-lxc-100/pedikur/app/routers/visits.py`
- Create: `compose/proxmox-lxc-100/pedikur/app/templates/visit_close.html`
- Modify: `compose/proxmox-lxc-100/pedikur/tests/test_visits.py`

**Interfaces:**
- Produces: `visits.close(session, visit_id, price_overrides: dict[int, int] | None = None, findings: str | None = None, note: str | None = None) -> Visit`.
  `price_overrides` is keyed by `VisitItem.id`, values in integer cents.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_visits.py
def test_close_is_idempotent_under_a_double_tap(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        vid = visit.id
    with db.session() as s:
        visits.close(s, vid)
        visits.close(s, vid)          # the second tap must change nothing
    with db.session() as s:
        from app.models import Visit, VisitItem
        v = s.get(Visit, vid)
        items = s.query(VisitItem).filter_by(visit_id=vid).all()
        assert v.status == "done"
        assert len(items) == 1
        assert items[0].unit_price_cents == 2500


def test_close_snapshots_the_price_at_closing_time(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        vid = visit.id
    with db.session() as s:
        treatments.update(s, fixtures["ped"], price_cents=2800)
    with db.session() as s:
        visits.close(s, vid)
    with db.session() as s:
        from app.models import VisitItem
        item = s.query(VisitItem).filter_by(visit_id=vid).one()
        assert item.unit_price_cents == 2800   # the price she charges today


def test_a_later_price_rise_does_not_rewrite_a_closed_visit(db, fixtures):
    with db.session() as s:
        visit = visits.book(s, fixtures["client_id"], _local(2026, 9, 10, 10),
                            [fixtures["ped"]], created_by="1")
        vid = visit.id
    with db.session() as s:
        visits.close(s, vid)
    with db.session() as s:
        treatments.update(s, fixtures["ped"], price_cents=9900)
    with db.session() as s:
        from app.models import VisitItem
        assert s.query(VisitItem).filter_by(visit_id=vid).one().unit_price_cents == 2500


def test_unclosed_lists_only_past_planned_visits(db, fixtures):
    past = timeutil.local_now() - timedelta(days=1)
    future = timeutil.local_now() + timedelta(days=1)
    with db.session() as s:
        old = visits.book(s, fixtures["client_id"], past, [fixtures["ped"]],
                          created_by="1")
        visits.book(s, fixtures["client_id"], future, [fixtures["gel"]],
                    created_by="1")
        old_id = old.id
    with db.session() as s:
        assert [v.id for v in visits.unclosed(s)] == [old_id]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_visits.py -v`
Expected: FAIL, `AttributeError: module 'app.services.visits' has no attribute 'close'`

- [ ] **Step 3: Add `close()` to `app/services/visits.py`**

```python
def close(session: Session, visit_id: int,
          price_overrides: dict[int, int] | None = None,
          findings: str | None = None, note: str | None = None) -> Visit:
    """Mark a Visit done and fix its prices.

    Idempotent on purpose: a double tap on a phone, or a retried request, must
    not post the line twice. The guard also stops a Visit closed months ago
    from being re-priced if the route is hit again.

    The price written is the Treatment's price at closing time, because nothing
    was quoted to the client in writing; the closing screen can override it per
    line.
    """
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    if visit.status == "done":
        return visit

    overrides = price_overrides or {}
    for item in visit.items:
        if item.kind != "treatment" or item.treatment is None:
            continue
        item.unit_price_cents = overrides.get(item.id, item.treatment.price_cents)

    if findings is not None:
        visit.findings = findings or None
    if note is not None:
        visit.note = note or None
    visit.status = "done"
    session.flush()
    return visit
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_visits.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Add the closing routes**

```python
# append to app/routers/visits.py
from app.services import visits as visit_service   # already imported as visits


@router.get("/{visit_id}/close")
def close_form(request: Request, visit_id: int,
               user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        visit = s.get(Visit, visit_id)
        if visit is None:
            return RedirectResponse("/", status_code=303)
        return request.app.state.templates.TemplateResponse(
            request, "visit_close.html",
            {"user": user, "tab": "today", "visit": visit,
             "treatments": treatments.list_active(s)})


@router.post("/{visit_id}/close")
def close(request: Request, visit_id: int,
          findings: str = Form(""), note: str = Form(""),
          user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        visits.close(s, visit_id, findings=findings, note=note)
    return RedirectResponse("/", status_code=303)


@router.post("/{visit_id}/status")
def status(request: Request, visit_id: int, value: str = Form(...),
           user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        visits.set_status(s, visit_id, value)
    return RedirectResponse("/", status_code=303)


@router.post("/{visit_id}/treatments")
def add_treatment(request: Request, visit_id: int,
                  treatment_id: int = Form(...),
                  user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        visits.add_treatment(s, visit_id, treatment_id)
    return RedirectResponse(f"/visits/{visit_id}/close", status_code=303)
```

Add `Visit` to the `from app.models import User` line at the top of the module.

- [ ] **Step 6: Write `templates/visit_close.html`**

The layout is the requirement, not decoration: the Done button comes first and
alone. Everything optional sits below it, never in front of it.

```html
{% extends "base.html" %}
{% block heading %}{{ visit.client.name }}{% endblock %}
{% block body %}
{% if visit.client.alert %}
<p class="alert-banner"><strong>{{ S["alert_label"] }}:</strong> {{ visit.client.alert }}</p>
{% endif %}

<p class="muted">
  {{ visit.starts_at | localtime }} - {{ visit.ends_at | localtime }}
</p>

<form method="post" action="/visits/{{ visit.id }}/close">
  <ul class="list">
    {% for item in visit.items if item.kind == 'treatment' %}
    <li class="row">
      <span>{{ item.treatment.name }}</span>
      <strong>{{ item.treatment.price_cents | eur }}</strong>
    </li>
    {% endfor %}
  </ul>

  <button type="submit" class="primary-big">{{ S["done"] }}</button>

  <details>
    <summary>{{ S["more_options"] }}</summary>
    <label for="findings">{{ S["findings"] }}</label>
    <textarea id="findings" name="findings" rows="2">{{ visit.findings or '' }}</textarea>
    <label for="note">{{ S["note"] }}</label>
    <textarea id="note" name="note" rows="2">{{ visit.note or '' }}</textarea>
  </details>
</form>

<details class="card">
  <summary>{{ S["add_treatment"] }}</summary>
  <form method="post" action="/visits/{{ visit.id }}/treatments">
    <select name="treatment_id" required>
      {% for t in treatments %}
      <option value="{{ t.id }}">{{ t.name }} - {{ t.price_cents | eur }}</option>
      {% endfor %}
    </select>
    <button type="submit" class="secondary">{{ S["add"] }}</button>
  </form>
</details>

<form method="post" action="/visits/{{ visit.id }}/status" class="row">
  <button name="value" value="cancelled" class="secondary">{{ S["cancelled"] }}</button>
  <button name="value" value="no_show" class="secondary">{{ S["no_show"] }}</button>
</form>
{% endblock %}
```

```css
/* app.css */
.primary-big {
  width: 100%;
  min-height: calc(var(--tap) * 1.4);
  font-size: var(--step-1);
  margin: var(--gap-4) 0;
}
```

Add to `strings/hu.py`: `done` "Kész", `more_options` "Továbbiak",
`findings` "Amit talált", `note` "Amit csinált", `add_treatment`
"Kezelés hozzáadása", `add` "Hozzáad", `cancelled` "Lemondta",
`no_show` "Nem jött el".

- [ ] **Step 7: Screenshot and time the flow**

```bash
node scripts/shot.mjs http://localhost:8000/visits/1/close /tmp/close.png 390 1000
```

Check on the image that the Done button is reachable with a thumb without
scrolling, and that no optional control sits above it.

- [ ] **Step 8: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): one-tap visit closing, idempotent under a double tap"
```

---

### Task 9: The Today screen, walk-ins and the PWA shell

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/app/routers/today.py`
- Create: `compose/proxmox-lxc-100/pedikur/app/templates/today.html`
- Create: `compose/proxmox-lxc-100/pedikur/app/static/{manifest.json,sw.js}`
- Modify: `compose/proxmox-lxc-100/pedikur/app/{main.py,templates/base.html,templates/login.html}`

**Interfaces:**
- Consumes: `visits.unclosed`, `schedule.week_grid`, `clients.search`, `treatments.list_active`.
- Produces: the `GET /` route (Today) and `POST /walk-in`.

- [ ] **Step 1: Write `app/routers/today.py`**

```python
from datetime import timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app import security
from app.models import User, Visit
from app.services import clients, timeutil, treatments, visits

router = APIRouter()


@router.get("/")
def today(request: Request, user: User = Depends(security.require_user)):
    now = timeutil.local_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    with request.app.state.db.session() as s:
        rows = list(s.scalars(
            select(Visit)
            .where(Visit.deleted_at.is_(None),
                   Visit.starts_at >= timeutil.to_utc_iso(start),
                   Visit.starts_at < timeutil.to_utc_iso(start + timedelta(days=1)))
            .order_by(Visit.starts_at)))
        pending = visits.unclosed(s)
        return request.app.state.templates.TemplateResponse(
            request, "today.html",
            {"user": user, "tab": "today", "visits": rows,
             "unclosed": pending, "today": now.date(),
             "clients": clients.search(s, ""),
             "treatments": treatments.list_active(s)})


@router.post("/walk-in")
def walk_in(request: Request, client_id: int = Form(...),
            treatment_ids: list[int] = Form(...),
            user: User = Depends(security.require_user)):
    """A client who arrives without a booking still gets a Visit row: one
    client session is one Visit, whether it was booked or not."""
    now = timeutil.local_now().replace(second=0, microsecond=0)
    with request.app.state.db.session() as s:
        try:
            visit = visits.book(s, client_id, now, treatment_ids,
                                created_by=str(user.id))
        except visits.SlotTaken:
            # A walk-in during another Visit is a real situation, not an error.
            # Start it at the end of whatever is running.
            # A zero-length window never overlaps anything, so probe a
            # one-minute window instead.
            running = visits.overlapping(
                s, timeutil.to_utc_iso(now),
                timeutil.to_utc_iso(now + timedelta(minutes=1)))
            latest = max(timeutil.from_utc_iso(v.ends_at) for v in running)
            visit = visits.book(s, client_id, latest, treatment_ids,
                                created_by=str(user.id))
        visit_id = visit.id
    return RedirectResponse(f"/visits/{visit_id}/close", status_code=303)
```

- [ ] **Step 2: Write `templates/today.html`**

```html
{% extends "base.html" %}
{% block heading %}{{ S["nav_today"] }} - {{ today.strftime("%m. %d.") }}{% endblock %}
{% block body %}
{% if unclosed %}
<a class="banner-warning" href="/calendar">
  {{ unclosed | length }} {{ S["unclosed_visits"] }}
</a>
{% endif %}

<ul class="list">
  {% for v in visits %}
  <li>
    <a class="card row is-{{ v.status }}" href="/visits/{{ v.id }}/close">
      <strong class="time">{{ v.starts_at | localtime }}</strong>
      {% if v.client.alert %}<span class="alert-dot" aria-label="{{ S['has_alert'] }}"></span>{% endif %}
      <span>{{ v.client.name }}</span>
      <span class="muted">
        {%- for i in v.items if i.kind == 'treatment' -%}
          {{ i.treatment.name }}{% if not loop.last %}, {% endif %}
        {%- endfor -%}
      </span>
    </a>
  </li>
  {% else %}
  <li class="muted">{{ S["no_visits_today"] }}</li>
  {% endfor %}
</ul>

<details class="card">
  <summary>{{ S["walk_in"] }}</summary>
  <form method="post" action="/walk-in">
    <label for="wc">{{ S["client"] }}</label>
    <select id="wc" name="client_id" required>
      {% for c in clients %}<option value="{{ c.id }}">{{ c.name }}</option>{% endfor %}
    </select>
    <label>{{ S["treatments_title"] }}</label>
    {% for t in treatments %}
    <label class="check">
      <input type="checkbox" name="treatment_ids" value="{{ t.id }}"> {{ t.name }}
    </label>
    {% endfor %}
    <button type="submit">{{ S["start"] }}</button>
  </form>
</details>
{% endblock %}
```

```css
/* app.css */
.banner-warning {
  display: block;
  padding: var(--gap-3);
  margin-bottom: var(--gap-3);
  border-radius: var(--radius);
  background: color-mix(in srgb, var(--danger) 12%, var(--surface));
  border: 1px solid var(--danger);
  color: var(--ink);
  text-decoration: none;
  font-weight: 600;
}
.row { display: flex; align-items: center; gap: var(--gap-3); }
.time { font-variant-numeric: tabular-nums; }
.muted { color: var(--ink-muted); }
.list { list-style: none; margin: 0; padding: 0;
        display: grid; gap: var(--gap-2); }
```

Add to `strings/hu.py`: `unclosed_visits` "lezáratlan látogatás",
`no_visits_today` "Ma nincs bejegyzett látogatás", `walk_in` "Beeső kliens",
`start` "Indítás".

- [ ] **Step 3: Write the PWA files**

```json
{
  "name": "Pedikur",
  "short_name": "Pedikur",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#f7f6f4",
  "theme_color": "#f7f6f4",
  "icons": [
    { "src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

```javascript
// static/sw.js
// Read-only convenience: the day's list survives a dead connection.
// Nothing is queued or written offline; the premises have wifi.
const CACHE = 'pedikur-v1';
const ASSETS = ['/static/tokens.css', '/static/app.css', '/static/htmx.min.js'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) =>
    Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  if (url.pathname !== '/' && !url.pathname.startsWith('/static/')) return;

  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
```

Register it in `base.html` before `</body>`, and clear the caches on the login
page so a logged-out device keeps no copy of the day's client names:

```html
<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js');
  }
</script>
```

```html
<!-- in login.html, inside the block -->
<script>
  if ('caches' in window) { caches.keys().then(ks => ks.forEach(k => caches.delete(k))); }
</script>
```

Create `icon-192.png` and `icon-512.png`: a plain square in `--accent` with a
white "P". Any drawing tool or a one-line ImageMagick call is fine; they are
placeholders for the launcher, not brand assets.

- [ ] **Step 4: Wire the routers into `app/main.py`**

```python
from app.routers import auth, calendar, clients, settings, today, visits as visits_router

app.include_router(auth.router)
app.include_router(today.router)
app.include_router(calendar.router)
app.include_router(clients.router)
app.include_router(visits_router.router)
app.include_router(settings.router)
```

- [ ] **Step 5: Walk the whole flow by hand and screenshot each step**

```bash
node scripts/shot.mjs http://localhost:8000/ /tmp/today.png 390 1100
```

Book a Visit from the calendar, close it in one tap, confirm it appears in the
client's history, and confirm the unclosed banner appears for a Visit whose
window has passed. Judge every screen from the image, not from the markup.

- [ ] **Step 6: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): today screen, walk-ins and the PWA shell"
```

---

### Task 10: The JSON API, its token, and the stack README

**Files:**
- Create: `compose/proxmox-lxc-100/pedikur/app/routers/api.py`
- Create: `compose/proxmox-lxc-100/pedikur/README.md`
- Modify: `compose/proxmox-lxc-100/pedikur/app/main.py`
- Test: `compose/proxmox-lxc-100/pedikur/tests/test_api.py`

**Interfaces:**
- Produces: `GET /api/clients`, `GET /api/visits?from=&to=`, `GET /api/treatments`,
  `POST /api/clients`, `POST /api/visits`, all requiring
  `Authorization: Bearer <PEDIKUR_API_TOKEN>`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api.py
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PEDIKUR_DATA", str(tmp_path))
    monkeypatch.setenv("PEDIKUR_SECRET_KEY", "test-secret-key-for-sessions")
    monkeypatch.setenv("PEDIKUR_API_TOKEN", "test-token")
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_api_requires_a_bearer_token(client):
    assert client.get("/api/clients").status_code == 401
    assert client.get("/api/clients",
                      headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_api_returns_json_with_a_valid_token(client):
    res = client.get("/api/clients", headers={"Authorization": "Bearer test-token"})
    assert res.status_code == 200
    assert res.json() == []


def test_health_needs_no_token(client):
    assert client.get("/health").status_code == 200
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL with 404 on `/api/clients`

- [ ] **Step 3: Write `app/routers/api.py`**

```python
"""JSON surface for scripting and, from phase 4, an MCP server.

Reachable only from the internal network: the reverse proxy denies /api/* on
the public route, and the MCP host talks to 192.168.0.110 directly. The token
is the second layer, because our own rule says we do not trust a proxy config
to be right - including our own deny rule.
"""
from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, Body, Header, HTTPException, Request, status
from sqlalchemy import select

from app.models import Visit
from app.services import clients, timeutil, treatments, visits

router = APIRouter(prefix="/api")


def _authorise(request: Request, authorization: str | None) -> None:
    expected = request.app.state.settings.api_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    presented = authorization.removeprefix("Bearer ")
    if not secrets.compare_digest(presented, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@router.get("/clients")
def api_clients(request: Request, q: str = "",
                authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    with request.app.state.db.session() as s:
        return [{"id": c.id, "name": c.name, "phone": c.phone,
                 "has_alert": c.has_alert} for c in clients.search(s, q)]


@router.get("/treatments")
def api_treatments(request: Request,
                   authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    with request.app.state.db.session() as s:
        return [{"id": t.id, "name": t.name, "duration_min": t.duration_min,
                 "price_cents": t.price_cents, "active": bool(t.active)}
                for t in treatments.list_all(s)]


@router.get("/visits")
def api_visits(request: Request, date_from: str, date_to: str,
               authorization: str | None = Header(default=None)):
    """date_from and date_to are local dates, YYYY-MM-DD, inclusive of from
    and exclusive of to."""
    _authorise(request, authorization)
    start = datetime.fromisoformat(f"{date_from}T00:00").replace(tzinfo=timeutil.LOCAL)
    end = datetime.fromisoformat(f"{date_to}T00:00").replace(tzinfo=timeutil.LOCAL)
    with request.app.state.db.session() as s:
        rows = s.scalars(
            select(Visit).where(
                Visit.deleted_at.is_(None),
                Visit.starts_at >= timeutil.to_utc_iso(start),
                Visit.starts_at < timeutil.to_utc_iso(end)
            ).order_by(Visit.starts_at))
        return [{
            "id": v.id,
            "client": v.client.name,
            "starts_at": v.starts_at,
            "ends_at": v.ends_at,
            "status": v.status,
            "total_cents": sum(i.unit_price_cents * i.qty for i in v.items),
            "treatments": [i.treatment.name for i in v.items
                           if i.kind == "treatment" and i.treatment],
        } for v in rows]


@router.post("/clients", status_code=201)
def api_create_client(request: Request, payload: dict = Body(...),
                      authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    with request.app.state.db.session() as s:
        client = clients.create(s, payload["name"], payload.get("phone"),
                                created_by="api")
        return {"id": client.id}


@router.post("/visits", status_code=201)
def api_create_visit(request: Request, payload: dict = Body(...),
                     authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    starts = datetime.fromisoformat(payload["starts_at"]).replace(
        tzinfo=timeutil.LOCAL)
    with request.app.state.db.session() as s:
        try:
            visit = visits.book(s, payload["client_id"], starts,
                                payload["treatment_ids"], created_by="api")
        except visits.SlotTaken:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="slot taken")
        return {"id": visit.id}
```

There is deliberately no `Erase` endpoint. It is the only irreversible
operation in the system and no machine use case needs it.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: PASS, the whole suite

- [ ] **Step 5: Write the stack README**

```markdown
# pedikur

Pedicure practice management. Spec:
`docs/superpowers/specs/2026-09-05-pedikur-design.md`.

## Run

Deployed by Komodo from this repo. Secrets (`PEDIKUR_SECRET_KEY`,
`PEDIKUR_API_TOKEN`) live in the Komodo Stack Environment, never in git.

    docker compose up -d
    docker compose exec pedikur python -m app.cli create-user <name> "<Full Name>" --admin

## Reverse proxy

The public route through Pangolin serves the UI only. `/api/*` must be denied
there: the JSON surface can write, and it is reached from the internal network
at `192.168.0.110:3010` with a bearer token.

## Password reset

There is no mail server.

    docker compose exec pedikur python -m app.cli reset-password <username>

## Backup

The app snapshots itself nightly into `/data/backup` using SQLite's online
backup, keeping seven copies, and again before every schema migration. A live
WAL database must never be copied with `cp`. Restic then carries `/data`.

## Restore

    docker compose stop pedikur
    cp /srv/docker-data/pedikur/backup/daily-<stamp>.sqlite \
       /srv/docker-data/pedikur/db.sqlite
    docker compose start pedikur

Loses at most one day of entries.

## Rollback a bad deploy

Redeploy the previous commit in Komodo. Migrations are additive within a
release, so the older code tolerates the newer schema.
```

- [ ] **Step 6: Commit**

```bash
git add compose/proxmox-lxc-100/pedikur
git commit -m "feat(pedikur): internal JSON API with bearer auth, and the stack README"
```

---

## Definition of done for phase 1

All ten tasks committed, `python -m pytest tests/ -v` green, and the flow
walked by hand on a phone-sized viewport: log in, add a client, add a
treatment, book from the week grid, close in one tap, see it in the client's
history, and see the unclosed banner for a Visit whose window has passed.

The real measure is not that it runs. It is that the paper diary can be put
down.
