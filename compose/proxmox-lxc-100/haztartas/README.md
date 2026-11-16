# haztartas

Household budget for the family. Spec:
`docs/superpowers/specs/2026-11-15-haztartas-design.md`, design direction in
`DESIGN.md`.

One FastAPI container serving server-rendered Jinja templates over a single
SQLite file in WAL mode, installable as a PWA with an offline capture queue.
Host port 3011 on LXC 100.

## First install on a new host

The container runs as uid 1000 and Docker creates a missing bind mount source
as `root:root`. Without this the app cannot create its database and
crash-loops on `sqlite3.OperationalError: unable to open database file`:

    mkdir -p /srv/docker-data/haztartas
    chown 1000:1000 /srv/docker-data/haztartas

## Run

Deployed by Komodo from this repo. `HAZTARTAS_SECRET_KEY` lives in the Komodo
Stack Environment, never in git; generate it with:

    python -c "import secrets;print(secrets.token_urlsafe(48))"

An empty key is refused as well as an unset one, so a half-filled environment
stops the deploy rather than signing every session with an empty key.

    docker compose up -d
    curl -s 192.168.0.110:3011/health      # ok

`HAZTARTAS_HTTPS_ONLY` defaults to 1 and stamps the session cookie `Secure`.
Set it to 0 only to reach the app over plain http on the LAN or in the
screenshot loop: a browser drops a `Secure` cookie on an http origin and the
login form just reloads. `HAZTARTAS_FX_FETCH` defaults to on; 0 is for tests
only (see `.env.example`).

## Users

    docker compose exec haztartas python -m app.cli create-user <username> "<Full Name>" --role adult
    docker compose exec haztartas python -m app.cli create-user <username> "<Full Name>" --role child

Roles are `adult` and `child`; a child also gets a pocket-money wallet. The
password is asked for twice and is at least 10 characters. Passwords go to the
family directly, never into the repo, a chat or a log.

## Reverse proxy

Public route through Pangolin as `haztartas.example` (placeholder; the real
subdomain stays out of the docs), target `192.168.0.110:3011`. Resource rules,
in this order:

1. Bypass, country SK
2. Bypass, country HU
3. everything else: Pangolin SSO

Do not block `/capture/sync` or any other path: the offline queue uploads
there from the phone, and the whole app is one UI surface. Abroad, a request
without a Pangolin session is redirected to the SSO login; the queue treats
that as "not uploaded" and keeps the item.

The app's `origin_guard` (CSRF) accepts a POST whose `Origin` matches `Host`
or `X-Forwarded-Host`. After creating the resource, verify once from outside
(mobile data, not the LAN) that a real form POST works: log in on
`https://haztartas.example/login`, then save one entry. A guard rejection is
a bare `403` with the plain text body `forbidden` and no Pangolin styling. A
Pangolin 403 is an HTML page from Pangolin itself (or a redirect to its login),
so the body tells them apart. A guard 403 means Pangolin is not passing the
original host through.

## Offline capture

The service worker serves `/capture` from cache with the network off. An entry
recorded offline is kept in IndexedDB on the phone and uploaded when the
connection returns, exactly once. The page-wide counter shows how many wait. A
refused item of the logged-in user is listed with its reason and can be removed
from the phone. Another user's queued items on a shared phone are only counted,
with nothing of their content shown, and upload when that user logs back in.
Logging out empties the cache but not the queue. Abroad, where
Pangolin answers `/capture` itself with a redirect to its SSO login, the cached
form opens anyway and what is recorded waits in the queue until the phone is
back home.

Proof in a real Chrome against a running app with an empty month:

    node scripts/offline_check.mjs http://127.0.0.1:3011 <username> <password>

It runs the offline, expired-session, logout, Pangolin-redirect (on the upload
and on the form itself), full-storage and refused-item scenarios. Run it against a throwaway instance, not the
family's data.

## Password reset

There is no mail server.

    docker compose exec haztartas python -m app.cli reset-password <username>

## Backup

The app snapshots itself into `/data/backup` using SQLite's online backup,
once at start and then nightly, keeping seven `daily-*.sqlite` copies, and
again before every schema migration, keeping five of those. A live WAL
database must never be copied with `cp`.

Off the container, the whole of LXC 100 is in the nightly Proxmox vzdump at
02:00 to `/mnt/storage/backup/proxmox`, snapshot mode. That is what carries
`/srv/docker-data/haztartas`. The pve restic job does not: it backs up the
Proxmox host's own `/`.

Both copies live on the same machine. There is no offsite copy, by the owner's
decision on 2026-11-15 (spec section 10): a fire or theft at home takes the
data and its backup together. The in-app copies cover the database only, not
`media/`.

## Restore

    docker compose stop haztartas
    rm -f /srv/docker-data/haztartas/db.sqlite-wal \
          /srv/docker-data/haztartas/db.sqlite-shm
    cp /srv/docker-data/haztartas/backup/daily-<stamp>.sqlite \
       /srv/docker-data/haztartas/db.sqlite
    docker compose start haztartas

Loses at most one day of entries. The `rm` comes before the copy and is not
optional: SQLite replays any `db.sqlite-wal` it finds onto whatever
`db.sqlite` sits next to it, the restored backup included, so a WAL left
over from a crash would write newer pages over the old copy (measured
2026-11-15: a row written after the backup reappeared in the restored
database). Check a copy first with `sqlite3 <file> 'PRAGMA integrity_check'`,
which must print `ok`.

## Rollback a bad deploy

Redeploy the previous commit in Komodo. Migrations are additive within a
release, so the older code tolerates the newer schema. If a migration itself
went wrong, restore the `pre-migration-*` copy from `backup/` as above.

## Tests

The image carries no tests (`.dockerignore`), so they run on the host, from
this directory, in a throwaway environment built from `requirements.txt`
(pytest is pinned there) on the image's Python:

    uv run --no-project --python 3.13 --with-requirements requirements.txt \
      python -m pytest -q -p no:cacheprovider
