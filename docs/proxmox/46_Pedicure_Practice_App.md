**Date:** 2026-09-07
**Host:** LXC 100 docker-host (192.168.0.110), port 3010
**Public route:** `https://your-pedikur.yourdomain.com` via Pangolin (Hetzner VPS)

---

# Writing an Appointment Book, and the Ten Things That Were Wrong

This is the first application in this homelab that was written rather than deployed. It
replaces a paper appointment diary for a pedicure practice: log in, keep clients and a
price list, see the week, book by tapping an empty slot, and close a visit in one tap.

The interesting part is not that it works. It is the list of defects that a plan, a test
suite, a fresh-eyes review of every diff, and finally a real HTTPS deployment each caught,
and that the previous stage had missed. They are listed here because eight of the ten
generalise well beyond this app.

**250 tests, ten tasks, fifteen review findings acted on.** The whole flow was walked by
hand at 390px at the end: log in, add a treatment and a client, book from the week grid,
close in one tap, and find the visit in the client's history.

---

## The stack, and what it deliberately does not have

| | |
|---|---|
| Runtime | Python 3.13, FastAPI, Uvicorn, one container |
| Templates | Jinja2, server-rendered, htmx 2.0.10 vendored into `static/` |
| Database | SQLite in WAL mode, one file, SQLAlchemy 2.0 |
| Frontend build | none |
| Dependencies added at runtime | none |

No npm, no bundler, no build step: the CSS and the one JavaScript file are written by hand
and served as they are. A single practitioner on a phone does not need a SPA, and every
build step is something that breaks in two years when nobody remembers how to run it.

Money is integer cents everywhere. Every timestamp is stored as UTC ISO-8601 text with a
`Z`, and rendered in `Europe/Bratislava`. Working hours are the exception and are wall
clock `HH:MM` strings that never pass through a timezone conversion, because converting
09:00 would move opening time twice a year in the wrong direction.

---

## How it was built

A written plan, ten tasks, each with its own tests. After each task's commit, a subagent
with no memory of the working session reviewed the diff against the plan and the spec.
The reviewer got exactly three things: `git show`, the task's section of the plan, and the
spec. Screens were judged from screenshots, never from the markup, because a diff cannot
show that a name is clipped or that a column is misaligned.

That division mattered. The reviews found the logic defects; the screenshots found the
layout defects; and the tests found neither until they were written to.

---

## The ten defects

### 1. `executescript()` commits, so the migration transaction did not exist

The migration runner wrapped each file in `with con:` and believed it had a transaction.
`sqlite3.Connection.executescript()` commits any open transaction and performs no
transaction control of its own, so the `with` block wrapped only the bookkeeping insert.
Measured, with a migration whose second statement is valid and whose third is not:

```
raised: OperationalError near "IS": syntax error
tables: ['t', 'ok']          <- the half-applied migration's table survived
```

`ok` was committed, nothing was recorded in `schema_version`, and every restart after that
died on "duplicate column name" with no way forward but manual `sqlite3` surgery. Fixing
the migration file did not help. The `BEGIN` and `COMMIT` have to be part of the script:

```
fix tables: ['t']            <- nothing survived
```

### 2. Check-then-write is a race until the transaction begins IMMEDIATE

The booking service checked for an overlapping appointment and then inserted, inside one
transaction, which the plan said was enough. It is not. pysqlite opens a transaction
lazily and only just before a write, so two bookings both read the slot as free and both
insert. Four threads on the same 10:00 slot:

```
before: [(0, 'booked'), (1, 'booked')]      2 visits in the database
after:  1 booked, 3 SlotTaken               1 visit in the database
```

The fix is to take control of transaction handling and emit `BEGIN IMMEDIATE`, which takes
the write lock before the read:

```python
@event.listens_for(engine, "connect")
def _pragmas(dbapi_connection, _record):
    dbapi_connection.isolation_level = None      # stop pysqlite from deciding
    ...

@event.listens_for(engine, "begin")
def _begin_immediate(connection):
    connection.exec_driver_sql("BEGIN IMMEDIATE")
```

Every transaction now takes the write lock, reads included. Blunt, and right for one user
on one device.

The same defect had already appeared in the login throttle, where `user.failed_logins += 1`
is a read-modify-write. Ten parallel wrong passwords:

```
old (user.failed_logins += 1):  1 of 10 counted, account never locked
new (UPDATE ... = ... + 1):    10 of 10 counted, account locked
```

### 3. Two aware datetimes that share a tzinfo compare as wall clock

This one bit twice, in opposite directions, and is the least obvious thing in the whole
build. Python's rule: if both operands are aware and have the same `tzinfo`, the offset is
ignored and the naive fields are compared. Across a DST transition that means an end an
hour later in real time reads as *earlier* than its own start:

```
end_local < start_local          True    (wall clock)
to_utc(end) > to_utc(start)      True    (real time)
```

It broke an end-after-start guard, and before that it had broken the first DST test, which
measured 90 minutes for a 30-minute appointment. Every booking rule now converts to UTC
first and converts back only for display.

The grid is the deliberate exception: it is a wall clock, so it places blocks by wall-clock
minutes and computes the span from row numbers rather than from a subtraction.

### 4. SQLite folds case for ASCII only

The client search would have returned nothing for what anyone would actually type on a
phone, where the accented keys are the slow ones. Measured against test fixtures, using
the two spellings a Hungarian name can be typed in:

```
LIKE 'kovács'  -> ['Kovács Anna']     (exact case only)
LIKE 'KOVÁCS'  -> ['KOVÁCS Béla']
LIKE 'kovacs'  -> []
```

The fix is a deterministic SQLite function registered on connect that lower-cases and
strips combining marks, applied to both sides of the comparison. It also fixes list order:
SQLite's BINARY collation sorts every accented initial after `Z`.

One trap comes with it, and it is written into the code as a comment so nobody undoes it:
never build an index on that function. SQLite accepts the index, and the database then
cannot be written or even `PRAGMA integrity_check`ed by any connection that has not
registered the function, which is every `sqlite3` CLI and every restore verification.

### 5. Floor division gets the sign of money wrong

The currency filter was `f"{c // 100},{c % 100:02d} EUR"`. Python's `//` and `%` floor
towards minus infinity, so `-150 // 100` is `-2` and `-150 % 100` is `50`, and minus one
euro fifty rendered as `-2,50 EUR`. Nothing writes a negative price today; the moment a
result line or a correction does, every one is wrong by a euro.

Prices are parsed with `Decimal` and half-up rounding, never `float`: `18.5 * 100` is
`1850.0000000000002` in binary floating point, and the column has a
`CHECK (typeof(price_cents) = 'integer')` that refuses it.

### 6. Komodo deploys without rebuilding

The first real deployment came up dead with `Could not import module app.main`, on a repo
where that file had existed for nine commits. Komodo deploys with `docker compose up -d`,
which does **not** rebuild a `build:` service whose image already exists. It pulled all
seventeen commits and then recreated the container from the image built during the very
first one:

```
pedikur-pedikur:latest   2026-09-06 14:23:38
/srv/app: __init__.py backup.py config.py db.py migrate.py migrations
```

Five modules and no `main.py`. The fix is one line in the compose file:

```yaml
services:
  app:
    build: .
    pull_policy: build      # rebuild on every deploy
```

The worse half is what would have happened next: every future code change would have
deployed the same way, and an app that silently keeps serving the previous version is much
harder to notice than one that refuses to start. This applies to every self-building stack
in this repo and is now recorded in `AGENTS.md`.

### 7. Pangolin evaluates rules first-match-wins, whatever the UI says

The JSON API has to be denied on the public route: it can write, and it is meant to be
reached from the internal network with a bearer token, where the token is the second layer
rather than the only one. The rule was added, and the API was still reachable from the
internet with a valid token.

The dashboard says "rules are evaluated in descending order until one evaluates as true".
The source says:

```javascript
rules = rules.sort((a, b) => a.priority - b.priority);
for (const rule of rules) { ... return rule.action; }
```

Ascending priority, and the first match returns immediately. A `Bypass Auth / Country`
rule at priority 1 therefore shadowed the path block at priority 3 completely. The path
block has to come first:

```
1  Block Access   Path       /api/*
2  Bypass Auth    Country    ...
3  Bypass Auth    IP Range   172.18.0.0/16
4  Block Access   Country    ALL
```

The matcher splits the pattern on `/` and a `*` segment covers zero or more path segments,
so `/api/*` covers `/api` itself and any depth below it. Query strings are not part of the
path.

**Verifying a deny rule needs more than the status code.** After the reorder the API
answered `401` from outside, which is also what the app answers to a bad token. The proof
that Pangolin dropped it is in the response and the log:

```
outside:  HTTP/2 401, content-type: text/plain, body "Unauthorized", no `server` header
inside:   HTTP/1.1 200 OK, server: uvicorn, content-type: application/json
app log:  two /api/clients hits in three minutes, both 200, both from the internal gateway
```

FastAPI's 401 is JSON with a `WWW-Authenticate` header. The external requests never
reached the container at all.

### 8. Let's Encrypt fails on a DNS record that is minutes old

The certificate did not issue, and Traefik served `CN = TRAEFIK DEFAULT CERT`. The reason
was in the log, at the second the resource was created:

```
DNS problem: NXDOMAIN looking up A for your-pedikur.yourdomain.com
```

The record existed by the time anyone looked, but not when Traefik asked. Traefik does not
retry that within any useful time, so the fix is to restart it. Two things are worth doing
first, because a second failure consumes one of Let's Encrypt's five failed validations per
hostname per hour:

```bash
for r in 1.1.1.1 8.8.8.8 9.9.9.9; do dig +short @$r your-pedikur.yourdomain.com A; done
```

All three answered before the restart, and the certificate issued four seconds later.

### 9. A service worker's scope is the directory it is served from

Registered from `/static/sw.js`, the scope was `/static/`, and a service worker cannot
intercept anything outside its scope. The file exists to keep the day's list readable on a
dead connection and has an explicit branch for `/`; that branch could never have run.

```
before:  service worker: registered: https://your-pedikur.yourdomain.com/static/
after:   service worker: registered: https://your-pedikur.yourdomain.com/
```

Serving it from `/sw.js` puts the scope at the root. This one is only findable in
production: a service worker needs a secure context, so it does not register over plain
HTTP at all, and every local test ran over HTTP.

### 10. The backup section named the wrong backup

The stack's README said "Restic then carries `/data`". It does not. The restic job backs
up the Proxmox host's own `/`, and LXC 100's rootfs is an LVM thin volume that is not
mounted underneath it:

```
restic snapshots --latest 1  ->  48bf6384  2026-09-06  pve  /  21.364 GiB
ls /var/lib/lxc/100/rootfs/srv/docker-data/pedikur/  ->  No such file or directory
```

What actually carries it is the nightly Proxmox `vzdump` of the whole container at 02:00,
snapshot mode, 7 daily / 4 weekly / 3 monthly, and today's is real: 21.7 GB written at
02:06. The app also snapshots its own database into `/data/backup` with SQLite's online
backup, once at boot and then daily, and again before every schema migration.

A backup section is read exactly once, by someone who has already lost the data. It is the
worst place in a repository to be wrong.

---

## Two things the deployment needs that no file can express

**The bind mount owner.** The container runs as uid 1000, and Docker creates a missing bind
mount source as `root:root`. The image's own `chown` does not reach it, so the app cannot
create its database and crash-loops on `unable to open database file`. On a new host:

```bash
mkdir -p /srv/docker-data/pedikur
chown 1000:1000 /srv/docker-data/pedikur
```

**The Secure cookie.** Session cookies carry `Secure` by default. Over plain HTTP on the
LAN or over Tailscale, the browser drops the cookie and the login form simply reloads with
nothing to show for it, which looks exactly like a broken application. There is an
environment switch for that case, and the app logs a warning at startup when it is off.

---

## What the layers actually caught

| Layer | What only it found |
|---|---|
| Writing the tests first | the `add_treatment` stale-collection bug, before any of it ran |
| The test suite | the migration rollback, the throttle, the DST arithmetic |
| Fresh-eyes review of the diff | the closing double-book, an uncorrectable mistyped price, five routes that answered `500` instead of a message |
| Screenshots | a desktop layout with the content below the fold, a 146px header misalignment, three names clipped in the week grid |
| The real HTTPS deployment | the stale image, the rule order, the certificate, the service worker scope |

The last row is the one worth remembering. Four defects survived a plan, 250 tests and ten
reviews, and were found in the first twenty minutes of the app being reachable from the
internet. None of them could have been found any earlier, because each one needed something
that only exists in production: a rebuild, a reverse proxy, a certificate authority, and a
secure context.

---

## Known and not fixed

- **No offsite copy.** The container backup and the app's own snapshots both live on the
  same machine. This is the same posture as every other service here, and it is written
  down rather than assumed.
- **The geo-fence locks the practitioner out abroad.** The public route only accepts two countries, and
  a request from anywhere else is refused with a message that does not explain why.
- **A visit can be booked outside working hours.** The calendar widens to show it rather
  than hiding it, which is the honest behaviour, but nothing warns at booking time.
