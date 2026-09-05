# Pedikur: pedicure practice management - design

**Date:** 2026-09-05
**Status:** approved design, revised after a grilling pass the same day.
Implementation plan not yet written.
**Name:** `pedikur` - directory, container, database and URL

Terms in bold below are defined in the repo's root `CONTEXT.md` under
"Pedikur" and are used in their glossary sense throughout.

## 1. Context

A self-employed pedicurist working in Slovakia needs one place for clients,
**Visits**, treatment history, **Product** stock, and money. Today none of this
is tracked in a system. Two people will use it: the practitioner (daily work,
not IT literate) and the repo owner (admin).

The interface is built here rather than adopted, because no existing product
fits: the open-source salon tools (Easy!Appointments, Bookient, Sakura Saki)
are booking-first with no treatment notes, no consumable tracking and no
expense side, and the ERPs that do cover consumption (Odoo, Dolibarr, ERPNext)
cannot be shaped into a 15-second mobile visit log.

### What this is not

Tax and statutory bookkeeping are out of scope, by the owner's decision. The
app records the amount taken and optionally the scanned document, and
calculates from that. It does not produce statutory records.

## 2. Constraints

### Slovak legal boundary (researched 2026-09-05, informs scope only)

- **eKasa stays outside the app.** Act 384/2025 Z. z. on revenue recording
  took effect 2026-01-01, replacing 289/2008 Z. z. Pedicure, manicure and
  cosmetic services are covered. Every cash payment must go through eKasa
  (ORP, VRP2, or the newly recognised software cash register). Penalties start
  at EUR 330 and escalate. **The app never issues a receipt or an invoice.**
  Recorded as ADR-0003.
- The practitioner keeps using VRP2 (free, provided by Financna sprava, no
  monthly document limit). The overlap with our records is a single field, the
  amount; everything else we store (which client, which **Treatment**, which
  Products, notes) does not exist in eKasa. Two other options were considered
  and rejected for now: switching to a software cash register with a REST API
  (monthly cost, and it would put a certified cash register inside our
  dependency chain), and pulling data out of the eKasa zone (no documented
  free export API found).
- From 2026-01-01 the same act also requires offering cashless payment and
  permits sending the receipt electronically on request. Compliance items for
  the practitioner, unrelated to this app.
- **Act 385/2025 Z. z. lands 2027-01-01:** domestic B2B e-invoicing. The
  *issuing* duty applies to VAT payers only, but the duty to *receive*
  e-invoices applies to every taxable person regardless of VAT registration.
  From that date supplier invoices arrive as structured XML over Peppol.
  Design consequence: the document intake must not assume PDF forever.
  Voluntary phase from 2026 Q2.
- Retention: 5 years for a non-VAT-registered sole trader with no employees
  using flat-rate expenses or tax records; 10 years if keeping full accounts,
  VAT registered, or an employer (Act 431/2002 Z. z. s. 35).

### GDPR

Client foot conditions are health data, GDPR Article 9 special category
(Slovak implementation: Act 18/2018 Z. z.). Consequences carried into the
design: two independent authentication layers, **Archive** and **Erase** as
distinct operations, and this app's domain must not appear in `docs/`.

**What erasure cannot reach: the backups.** An Erase does not touch the seven
nightly SQLite copies or the restic snapshots. They age out on their own
schedule and are never restored selectively. If an old backup is ever
restored, the erasure must be run again. This is the accepted practice and it
belongs in writing rather than being improvised after a request arrives.

**Data is not encrypted at rest**, and that is deliberate: see ADR-0005.

### Working conditions

Fixed premises with reliable wifi. No offline-first requirement; the daily
Visit list is cached by a service worker for read-only fallback.

## 3. Architecture

One container, one file database, no build step.

```
compose/proxmox-lxc-100/pedikur/
  docker-compose.yml
  app/
    main.py          FastAPI: HTML routes + /api/* JSON routes
    models.py        SQLModel tables
    services/        business logic, called by both routers
    google_sync.py   freebusy poll, in-process asyncio task
    backup.py        nightly Connection.backup(), in-process asyncio task
    cli.py           admin commands (password reset)
    strings/hu.py    all user-facing text, keyed
    templates/       Jinja2
    static/          htmx 2.x, CSS, small vanilla JS
volume: /srv/docker-data/pedikur/{db.sqlite, media/, backup/}
```

**SQLite, not Postgres.** One user at a time, 13 tables, a few thousand rows a
year. WAL mode plus `busy_timeout=5000`. This removes a container, a password
and a backup target: the backup is one file into the existing restic
repository. FTS5 is available later if note search ever needs it. Postgres
becomes correct only if concurrent writers from separate machines appear,
which they will not.

**htmx with server-rendered Jinja, not an SPA.** No npm, no bundler, no client
state that can drift from the server's. The interface design lives in HTML and
CSS, so building it here is unaffected. Recorded as ADR-0006.

**Pin htmx 2.x, not 4.x.** htmx 4.0.0 was released 2026-08-28, but 2.x remains
`latest` on npm until early 2027, is feature-complete, and is supported
indefinitely. Version 4 swapped XHR for the Fetch API and renamed attributes;
there is no reason to take that now.

**Two routers, one service layer.** HTML routes render Jinja for the UI,
`/api/*` routes return JSON for the MCP server and for scripting. The logic
exists once.

**The Google sync and the nightly backup run in-process**, as asyncio tasks,
not as separate workers or host cron entries.

**Attachments live on disk**, not as blobs, and are served only to an
authenticated session.

**Hungarian interface, with the text extracted.** All user-facing strings sit
in a keyed module rather than inline in templates. One language ships; a
second one later is translation rather than a rewrite.

## 4. Access and authorisation

Reached over the internet through Pangolin on the Hetzner VPS (configured
separately by the owner), not over Tailscale.

- Two accounts. A single `is_admin` boolean, not a permission framework.
  Admin-only: user management, the Google connection, and **Erase**.
  Everything else is shared, including the price list and Product master data,
  which are daily work.
- **The app must never trust that it sits behind Pangolin.** Its own login
  asks for a password even when Pangolin SSO has already passed the request.
  One misconfiguration must not put health data on the internet.
- Passwords: `argon2-cffi` directly, Argon2id. passlib's future is uncertain
  and pwdlib exists to migrate between algorithms, which is not our problem
  with one algorithm and two users.
- Login throttling: `failed_logins` and `locked_until` on the user row, 15
  minute lock after 5 failures. A public login form gets brute forced.
- Session: signed cookie via Starlette `SessionMiddleware`, `HttpOnly`,
  `Secure`, `SameSite=Lax`, real expiry. Rotating `SECRET_KEY` logs everyone
  out; that is the emergency lever.
- No email password reset (no mail server). Admin CLI:
  `docker compose exec app python -m app.cli reset-password <user>`.

### The `/api/*` surface

Full read and write, so a script or the MCP server can do real work. The risk
is bounded by the path rather than by the permissions:

- **Not reachable through Pangolin.** The public route serves the UI only;
  the reverse proxy denies `/api/*`. The MCP server on LXC 109 reaches the app
  directly at `192.168.0.110` over the internal network. The machine path and
  the public path are not the same path.
- **A bearer token is still required**, held in `setting`, rotatable by the
  admin, never written to logs. Our own rule says we do not trust the proxy
  config to be right, and that applies to our own deny rule too.
- **Erase is not exposed on the API.** It is the only irreversible operation
  in the system and no machine use case needs it. Everything else an API write
  can get wrong is either soft-deletable or settled by a correcting **Stock
  Movement**.
- API writes are recorded with `created_by = 'api'`.

## 5. Data model

```
user                id, name, username, password_hash, is_admin,
                    failed_logins, locked_until

client              id, name, phone, email, address,
                    alert                  red banner: diabetes,
                                           anticoagulants, allergy
                    notes
                    interval_override_days NULL by default; wins over the
                                           computed Visit Interval
                    archived_at            Archive, reversible
                    erased_at              Erase, irreversible
                    created_by

visit               id, client_id, starts_at, ends_at,
                    status                 planned | done | cancelled | no_show
                    findings               what was observed
                    note                   what was done
                    google_event_id, google_sync_pending
                    deleted_at, created_by

visit_item          id, visit_id, kind (treatment|product),
                    treatment_id, product_id, qty, unit_price_cents
                    exactly one of treatment_id / product_id is set,
                    matching kind

attachment          id, visit_id, expense_id, path, caption, taken_at
                    exactly one of visit_id / expense_id is set

treatment           id, name, duration_min, price_cents, active, created_by
treatment_recipe    treatment_id, product_id, qty

product             id, name, unit (ml|db|g), min_stock, active,
                    archived_at, created_by
stock_movement      id, product_id, qty (signed), unit_cost_cents,
                    reason (purchase|opening|consumption|sale|correction|waste),
                    visit_id?, expense_id?, created_at, created_by, note
                    append-only: never edited, never deleted

expense             id, date, vendor, category, amount_cents, note,
                    deleted_at, created_by

working_hours       id, weekday, date, start, end, is_closed
                    exactly one of weekday / date is set: weekday rows are
                    the recurring default, date rows override that one day
                    start/end are local wall-clock times of day, not
                    timestamps: 09:00 stays 09:00 across a DST change
busy_block          starts_at, ends_at, source, fetched_at   Google cache
setting             key, value       OAuth token, buffer_min, API token,
                                     default_interval_days, calendar allowlist
```

Five decisions carry this model:

**Booking and treatment record are one table.** A `visit` row moves
`planned -> done` through `status`. A walk-in also gets a row, immediately
`done`. No join, no duplicated date, and a client's history is a filter.

**No price list versioning.** `visit_item.unit_price_cents` snapshots the
price at the moment the Visit is closed; `treatment.price_cents` is only the
current default. A price rise leaves last year's revenue untouched, and costs
no table. Which price applies at closing is the **Visit-time** price, because
nothing was quoted to the client in writing; the closing screen allows an
override.

**Stock is a sum, not a stored number.** No `current_stock` column; quantity is
the `SUM` over `stock_movement`. Instant at this scale, and it removes the
class of bug where movements and the stock figure drift apart.

**Cost is snapshotted the same way revenue is.** Every Stock Movement carries
`unit_cost_cents`: the real price on an inbound movement (purchase, opening
stock), and the last known purchase price at that moment on a consumption
movement. Margin is therefore a sum of stored numbers rather than a figure
recomputed against today's prices. Without this, buying the same lacquer at a
higher price in June would silently rewrite January's margin, which is the
same defect the revenue side was designed to avoid. A moving average would be
marginally more accurate and was rejected: the practitioner cannot check it
against a receipt, and an explainable number is worth more here.

**Money is never a float.** All amounts are integer cents, EUR.

**All timestamps are stored UTC and rendered in `Europe/Bratislava`**, except
`working_hours.start/end`, which are wall-clock times of day and must not be
converted. Storing local time for instants breaks twice a year; converting
opening hours breaks the same two days in the opposite direction.

## 6. Screens

One number drives the design: closing a **Visit** must be one tap.

- **Today** (phone home screen). Time, name, Treatment. A red bar on the row of
  any client with an `alert`, before it is opened. A "walk-in" button opens an
  immediately `done` Visit. A persistent banner at the top while any past
  Visit is still unclosed.
- **Close visit.** The booking already gives the Treatment and the price, so
  the default path is a single "Done" button: it writes the Visit Item at the
  current price and posts consumption from the **Treatment Recipe**.
  `+ product`, `+ note`, `+ photo` and the price override sit below the
  button, not before it. Getting this wrong kills the system within two weeks.
- **Photo:** `<input type="file" accept="image/*" capture="environment">`.
  Native, opens the camera, needs no library. Images are resized on upload to
  1600 px on the long edge; at five Visits a day with two photos each, the raw
  files would be roughly 10 GB a year and a nail bed does not need more.
- **New client is inline in the Visit flow**, not a separate menu: name,
  phone, save, continue. There is no import, so every regular client arrives
  through this form once, and it must not break the fast path.
- **Calendar (week).** Visits in colour, Google busy blocks in grey, buffers as
  a thin strip, free slots highlighted. Tapping a free slot opens a new Visit.
  No drag-and-drop in v1: click to create, click to edit. Moving a Visit
  happens once a day, not ten times.
- **Client card.** The red `alert` banner first, then contact details and
  "last seen 6 weeks ago", then history: date, Treatment, findings,
  attachments. Search is a plain `LIKE` on the name; FTS5 is unnecessary at a
  few hundred clients.
- **Recall List.** Its own menu entry, not a dashboard tile: this is the list
  that produces revenue. Each row shows where the interval came from, "6
  weeks, from history" or "6 weeks, set", because otherwise she cannot judge
  whether to trust it. A second view holds the clients past three times their
  interval.
- **Stock.** Products with computed quantity, anything under `min_stock`
  highlighted. Tap to record a purchase, correction or waste movement.
- **Expenses.** A single form: date, vendor, amount, document photos, and
  optionally line items that create the inbound Stock Movements. Buying
  lacquer is money out and stock in, and it should be typed once. An expense
  with no line items is just an expense.
- **Dashboard.** Per period: revenue, expenses, result; revenue by Treatment;
  **margin by Treatment**; no-show count. One chart, not five.
- **Settings.** Working hours, Treatments and their Recipes, `buffer_min`,
  Google connection and calendar allowlist (admin), users (admin).

Navigation: bottom bar on phone (Today / Calendar / Clients / More), sidebar on
laptop. The service worker caches the Today page and static assets, read-only.

## 7. Visit lifecycle

**Unclosed Visits are never closed automatically.** Auto-closing would invent
revenue from a client who may not have come; auto-marking `no_show` would
invent the opposite. Both lie quietly. Instead the Today screen carries a
banner ("2 unclosed visits") until they are dealt with.

This matters more than it looks: the **Visit Interval** counts only `done`
Visits, so an unclosed Visit makes a client look as though they never came,
and puts them on the Recall List weeks early. The error spreads rather than
staying put.

- **`cancelled`**: the client gave notice. The slot frees up **and the Google
  "Foglalt" event is deleted**, otherwise her phone still shows a free time as
  busy.
- **`no_show`**: no notice. The slot is lost, the time has passed, and the
  past Google event is left alone.
- Neither counts toward the Visit Interval.

**Visit Interval** is the median gap between a client's `done` Visits, not a
field she fills in. Below two `done` Visits it falls back to
`setting.default_interval_days` (42). `client.interval_override_days` wins
when set. Median rather than mean, so one six-month gap does not distort it.

**Recall List** excludes clients with a `planned` Visit ahead of them, and
shows only those between one and three times their interval overdue. Past
that they move to a separate view: they have stopped coming rather than being
late, and without the cap the top of the list fills with people who moved away
and she stops reading it.

## 8. Calendar and Google integration

**Free slot computation.** Busy is Visits (`planned` and `done`) union
`busy_block`. **Every busy interval is extended by `buffer_min` at its end**,
whether it came from a Visit or from Google - one rule, one implementation.
Free is the day's `working_hours` minus the extended busy set, with candidate
starts snapped to a 15 minute grid, keeping only slots where the requested
Treatment duration fits. No buffer at the end of the working day: a Visit may
end exactly at closing time.

**Booking re-checks availability inside the insert transaction.** Checking
first and inserting after is a race, even with two users and two tabs.

**Reading Google.** `freebusy.query` every 10 minutes for today plus 60 days,
replacing `busy_block` rows for that range. Scope `calendar.freebusy`: the
response contains busy intervals only, never event titles, attendees or
descriptions. The private calendar's contents are therefore never seen by this
app, which is the GDPR-preferable direction as well as the simpler one.

**Which calendars count is an explicit allowlist**, chosen by the admin in
settings, defaulting to `primary` alone. Querying everything would pull in
Google's automatic birthday and holiday calendars and mark those days fully
busy, and a `freebusy` response cannot be filtered afterwards because it does
not say which busy intervals came from all-day events. A busy interval that
covers the whole working day is rendered as a day header ("all-day
commitment") rather than as a wall in the grid: same effect on availability,
legible at a glance.

**The "Pedikur" calendar is written to and never read.** A hardcoded
exclusion, not a setting, because getting it wrong once is enough: our own
Visits would come back as external grey blocks under themselves.

The obvious alternative, polling Google's "secret address in iCal format", was
rejected: Google refreshes that feed roughly once every 24 hours server-side
and it cannot be forced faster, so a slot could show as free for a day after
it was booked. Google's CalDAV interface implements every report except
`free-busy-query`, so CalDAV is not a route either.

**Writing to Google.** The integration is otherwise asymmetric: we see her
calendar, Google does not see the Visits, so she could double-book herself
from her phone. On create or change, the app writes a neutral "Foglalt" event
into a dedicated "Pedikur" Google calendar - date and time only, no client
name - and stores `google_event_id`. Client identity and health data never
reach Google. This needs a wider scope than reading (`calendar.events`
family); **the exact minimal write scope is unverified and must be confirmed
during implementation.**

**Staleness is shown, never hidden.** If Google is unreachable the last cache
is kept and labelled with its age ("Google calendar: refreshed 47 minutes
ago"). Stale busy data presented as current is what produces double bookings.
Failed writes set `google_sync_pending` and are retried by the next 10 minute
cycle, **and any row still pending after 24 hours raises a visible warning**:
a revoked token fails permanently rather than transiently, and a silent retry
loop would quietly restore exactly the double-booking risk the write path
exists to remove.

OAuth consent is done once by the admin. The refresh token lives in `setting`,
the access token in memory.

## 9. Error handling

1. **Double tap on "Done"** would post consumption twice. The transition to
   `done` is idempotent: one transaction, and Stock Movements are written only
   if the Visit was not already `done`. This will happen in practice.
2. **Money is integer cents**, never float.
3. **Google outage**: cached busy blocks with a visible age, as above.
4. **Reverse proxy chain** (Pangolin -> newt -> app): without
   `--forwarded-allow-ips` and correct proxy-header handling, `Secure` cookies
   and redirects break. Verify when Pangolin is wired up.
5. Orphaned upload files after a failed insert are accepted; they cost bytes.

## 10. Testing

A small pytest suite covering four things, no framework ceremony, no
per-route tests:

- free slot computation, **including a case on the DST changeover Sunday**
- stock summation, the snapshotted unit cost, and the idempotent `done`
  transition
- margin calculation
- `freebusy` response handling from a mocked Google response

These are the places where a wrong number would appear silently.

## 11. Backup, restore and rollback

**A live WAL-mode SQLite database must not be copied with `cp`** - the result
is torn and opens only sometimes. A nightly asyncio task uses Python's
`sqlite3.Connection.backup()`, which is the same online backup operation as
the CLI's `.backup` without needing the CLI in the image, a cron entry, or the
host reaching into the container's volume.

Seven daily copies are kept; the existing restic job then carries them along
with `media/`. Attachments are plain files and need nothing special.

**Restore is proven, not assumed.** Add pedikur to `scripts/restore-test.sh`:
restore into a temp directory, run `PRAGMA integrity_check`, and count rows in
`client` and `visit`.

**Rollback paths, written down before they are needed:**

- A bad deploy: redeploy the previous commit in Komodo. No data loss, because
  schema migrations stay forward-compatible.
- Corrupted data: stop the container, copy back the most recent nightly
  backup file, start it. Loses at most one day of entries.

Both commands belong in the stack README; nobody invents them at night.

## 12. Deployment

Compose stack under `compose/proxmox-lxc-100/pedikur/`, `restart:
unless-stopped`, volume `/srv/docker-data/pedikur`, `TZ` from `.env`. Secrets
(`SECRET_KEY`, Google client id and secret, API bearer token) in the Komodo
Stack Environment, never in git. A `/health` endpoint with an Uptime Kuma
monitor.

**Unverified:** how Komodo handles a `build:` directive in this git-based
setup. Fallback is a GitHub Actions build pushed to ghcr.io, the way the docs
site already builds in CI.

## 13. Phases

1. Auth, clients, the Treatment catalogue, Visits, closing a Visit. The
   catalogue is not optional here: closing a Visit needs a Treatment's
   duration and price. Usable from this point, and data starts accumulating.
2. Products, Treatment Recipes, stock, expenses.
3. Google sync, free slot view.
4. Dashboard, Recall List, MCP server.

## 14. Rejected alternatives

- **Paperless-ngx for the document side.** The original idea, dropped on
  volume: 30 to 60 purchase documents a year, roughly 250 over five years. OCR,
  tagging and full-text search pay off in the thousands, not the hundreds, and
  the amount is typed in anyway because the app calculates from it. It would
  also be a new stack with its own backup and auth, plus a link to maintain
  between expense row and document. Revisit if she cannot find a receipt by
  scrolling, or past roughly 500 documents; the MCP servers for it are not
  going anywhere.
- **Directus as the backend.** Recommended first, then dropped in favour of
  writing the backend. Directus v12 (released 2026-05-26, announced
  2026-04-22) moved to the MSCL licence with an enforced free Core tier of 3
  user seats, 25 collections and 5 flows. Our shape fits comfortably, and the
  Open Innovation Grant (under USD 5M revenue and 50 employees) lifts the
  caps, but that is two licence changes in three years (BSL in 2023, MSCL in
  2026) for a tool meant to run unattended for years. Recorded as ADR-0004.
- **PocketBase.** MIT and a single Go binary, but v0.39.10 (2026-07-29) is
  still pre-1.0 and upstream states it is not recommended for
  production-critical applications without accepting occasional manual
  migration steps. A bad trade for a daily-use tool.
- **Cal.com as the scheduling and availability engine.** It does exactly the
  external-calendar and availability job. Rejected on 2026-04-15: the
  production codebase moved to a private repository and the public code was
  relicensed to MIT as `Cal.diy` without Teams, Workflows, Insights, SSO and
  API v1; API v1 was retired 2026-02-28. Not a base for a multi-year tool.
- **Odoo Community, Dolibarr, ERPNext.** Cover consumption and stock on paper,
  but the custom interface is a requirement and an ERP UI cannot become a
  15-second mobile visit log. Configuring one is more work than the 13 tables
  it replaces.
- **A client import.** There is no digital client list to import; the records
  are on paper and in her head. Every client who matters returns within one
  Visit Interval and is entered then, through the inline form in the Visit
  flow. Building an importer for a paper notebook is work with no output.
- **A full audit log table.** `created_by` on the tables that matter answers
  the question that will actually be asked - did this come from a person or
  from the API - without putting a layer on every write path and without a
  table that outgrows all the others combined.
- **SQLCipher and at-rest encryption.** See ADR-0005.

## 15. Assumptions to confirm

- Products are consumed only for now, with retail sale planned later: both
  `stock_movement` reasons exist in the model from the start, but only the
  consumption UI is built.
- Hosted on LXC 100, not the K3s cluster, because the cluster is at a separate
  location and this is a daily-use tool.
