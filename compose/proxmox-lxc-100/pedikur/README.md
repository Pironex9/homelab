# pedikur

Pedicure practice management. Spec:
`docs/superpowers/specs/2026-09-05-pedikur-design.md`, design direction in
`DESIGN.md`, decisions in `docs/adr/0003` to `0006`.

One FastAPI container serving server-rendered Jinja templates with htmx, over
a single SQLite file in WAL mode. Host port 3010 on LXC 100.

## First install on a new host

The container runs as uid 1000 and Docker creates a missing bind mount source
as `root:root`, which the image's own `chown` does not touch. Without this the
app cannot create its database and crash-loops on
`sqlite3.OperationalError: unable to open database file`:

    mkdir -p /srv/docker-data/pedikur
    chown 1000:1000 /srv/docker-data/pedikur

## Run

Deployed by Komodo from this repo. `PEDIKUR_SECRET_KEY` and
`PEDIKUR_API_TOKEN` live in the Komodo Stack Environment, never in git;
generate each with:

    python -c "import secrets;print(secrets.token_urlsafe(48))"

Both are refused when empty as well as when unset, so a half-filled
environment stops the deploy rather than signing every session with an empty
key.

    docker compose up -d
    docker compose exec pedikur python -m app.cli create-user <name> "<Full Name>" --admin

`PEDIKUR_HTTPS_ONLY` defaults to 1 and stamps the session cookie `Secure`. Set
it to 0 only to reach the app over plain http on the LAN or in the screenshot
loop: a browser drops a `Secure` cookie on an http origin and the login form
just reloads with nothing to show for it. The app logs a warning at startup
when it is off.

## Reverse proxy

The public route through Pangolin serves the UI only. `/api/*` must be denied
there: the JSON surface can write, and it is reached from the internal network
at `192.168.0.110:3010` with a bearer token.

## JSON API

`Authorization: Bearer $PEDIKUR_API_TOKEN` on every call.

    GET  /api/clients?q=            id, name, phone, has_alert
    GET  /api/treatments            id, name, duration_min, price_cents, active
    GET  /api/visits?from=&to=      local dates, from inclusive, to exclusive
    POST /api/clients               {"name": ..., "phone": ...}
    POST /api/visits                {"client_id", "starts_at", "treatment_ids"}

There is no Erase endpoint. It is the only irreversible operation in the
system and no machine use case needs it. `has_alert` is a boolean on purpose:
the wording of a client's health alert never leaves the app for a list.

Money is integer cents in both directions. `/health` needs no token; it is the
compose healthcheck and reveals nothing beyond the process being alive.

## Password reset

There is no mail server.

    docker compose exec pedikur python -m app.cli reset-password <username>

A password is at least 10 characters, asked for twice.

## Backup

The app snapshots itself into `/data/backup` using SQLite's online backup,
once at start and then daily, keeping seven copies, and again before every
schema migration, keeping five of those. A live WAL database must never be
copied with `cp`. Restic then carries `/data`.

## Restore

    docker compose stop pedikur
    cp /srv/docker-data/pedikur/backup/daily-<stamp>.sqlite \
       /srv/docker-data/pedikur/db.sqlite
    docker compose start pedikur

Loses at most one day of entries. The `db.sqlite-wal` and `db.sqlite-shm`
files next to it can be left alone: a WAL whose salt no longer matches the
database file is discarded rather than replayed, measured on this schema
rather than assumed.

## Rollback a bad deploy

Redeploy the previous commit in Komodo. Migrations are additive within a
release, so the older code tolerates the newer schema.

## Tests

    docker build -t pedikur-dev .
    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests -q

Run inside the image, not on the host: the host has neither the dependencies
nor the Python version the container ships.
