# Praxis: pedicure practice management - design

**Date:** 2026-09-05
**Status:** approved design, implementation plan not yet written
**Working name:** `praxis` (replaceable)

## 1. Context

A self-employed pedicurist working in Slovakia needs one place for clients,
appointments, treatment history, product stock, and money. Today none of this
is tracked in a system. Two people will use it: the practitioner (daily work,
not IT literate) and the repo owner (admin).

The interface is built here rather than adopted, because no existing product
fits: the open-source salon tools (Easy!Appointments, Bookient, Sakura Saki)
are booking-first with no treatment notes, no consumable tracking and no
expense side, and the ERPs that do cover consumption (Odoo, Dolibarr, ERPNext)
cannot be shaped into a 15-second mobile visit log.

### What this is not

Tax and statutory bookkeeping are explicitly out of scope, by the owner's
decision. The app records the amount taken and optionally the scanned
document, and calculates from that. It does not produce statutory records.

## 2. Constraints

### Slovak legal boundary (researched 2026-09-05, informs scope only)

- **eKasa stays outside the app.** Act 384/2025 Z. z. on revenue recording
  took effect 2026-01-01, replacing 289/2008 Z. z. Pedicure, manicure and
  cosmetic services are covered. Every cash payment must go through eKasa
  (ORP, VRP2, or the newly recognised software cash register). Penalties start
  at EUR 330 and escalate. **The app never issues a receipt or an invoice.**
- The practitioner keeps using VRP2 (free, provided by Financna sprava, no
  monthly document limit). The overlap with our records is a single field, the
  amount; everything else we store (which client, which treatment, which
  products, notes) does not exist in eKasa. Two other options were considered
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
design: two independent authentication layers, soft delete plus a real
client-erasure path, encrypted backups, and this app's domain must not appear
in `docs/`.

### Working conditions

Fixed premises with reliable wifi. No offline-first requirement; the daily
appointment list is cached by a service worker for read-only fallback.

## 3. Architecture

One container, one file database, no build step.

```
compose/proxmox-lxc-100/praxis/
  docker-compose.yml
  app/
    main.py          FastAPI: HTML routes + /api/* JSON routes
    models.py        SQLModel tables
    services/        business logic, called by both routers
    google_sync.py   freebusy poll, in-process asyncio task
    cli.py           admin commands (password reset)
    templates/       Jinja2
    static/          htmx 2.x, CSS, small vanilla JS
volume: /srv/docker-data/praxis/{db.sqlite, media/, backup/}
```

**SQLite, not Postgres.** One user at a time, about 13 tables, a few thousand
rows a year. WAL mode plus `busy_timeout=5000`. This removes a container, a
password and a backup target: the backup is one file into the existing restic
repository. FTS5 is available later if note search ever needs it. Postgres
becomes correct only if concurrent writers from separate machines appear,
which they will not.

**htmx with server-rendered Jinja, not an SPA.** No npm, no bundler, no client
state that can drift from the server's. The interface design lives in HTML and
CSS, so building it here is unaffected.

**Pin htmx 2.x, not 4.x.** htmx 4.0.0 was released 2026-08-28, but 2.x remains
`latest` on npm until early 2027, is feature-complete, and is supported
indefinitely. Version 4 swapped XHR for the Fetch API and renamed attributes;
there is no reason to take that now.

**Two routers, one service layer.** HTML routes render Jinja for the UI,
`/api/*` routes return JSON for the MCP server and for scripting. The logic
exists once.

**The Google sync runs in-process**, an asyncio task every 10 minutes, not a
separate worker container.

**Photos and scanned documents live on disk**, not as blobs, and are served
only to an authenticated session.

## 4. Access and authorisation

Reached over the internet through Pangolin on the Hetzner VPS (configured
separately by the owner), not over Tailscale.

- Two accounts. A single `is_admin` boolean, not a permission framework.
  Admin-only: user management, the Google connection, and hard delete.
  Everything else is shared, including the price list and product master data,
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
- Soft delete (`deleted_at`) everywhere. This is recoverability, not
  authorisation: a mistyped visit must be undoable.

## 5. Data model

```
user                id, name, username, password_hash, is_admin,
                    failed_logins, locked_until

client              id, name, phone, email, address,
                    alert              red banner: diabetes, anticoagulants, allergy
                    notes              general description
                    usual_interval_days
                    deleted_at

appointment         id, client_id, starts_at, ends_at,
                    status             planned | done | cancelled | no_show
                    findings           what was observed
                    note               what was done
                    google_event_id, google_sync_pending
                    deleted_at

appointment_item    id, appointment_id, kind (service|product),
                    service_id, product_id, qty, unit_price_cents
                    exactly one of service_id / product_id is set,
                    matching kind

photo               id, appointment_id, path, caption, taken_at

service             id, name, duration_min, price_cents, active
service_consumable  service_id, product_id, qty          the recipe

product             id, name, unit (ml|db|g), min_stock,
                    last_purchase_price_cents, active, deleted_at
stock_movement      id, product_id, qty (signed),
                    reason (purchase|consumption|sale|correction|waste),
                    appointment_id?, expense_id?, created_at, note

expense             id, date, vendor, category, amount_cents, note,
                    document_path, deleted_at

working_hours       id, weekday, date, start, end, is_closed
                    exactly one of weekday / date is set: weekday rows are
                    the recurring default, date rows override that one day
busy_block          starts_at, ends_at, source, fetched_at  Google cache
setting             key, value                              OAuth token, buffer_min
```

Three decisions carry this model:

**Appointment and visit are one table.** No separate `visit`: a row moves
`planned -> done` through `status`. A walk-in also gets an `appointment` row,
immediately `done`. No join, no duplicated date, and a client's history is a
filter.

**No price list versioning.** `appointment_item.unit_price_cents` snapshots
the price at the moment of the visit; `service.price_cents` is only the
current default. A price rise leaves last year's revenue untouched, and costs
no table.

**Stock is a sum, not a stored number.** No `current_stock` column; quantity is
the `SUM` over `stock_movement`. Instant at this scale, and it removes the
class of bug where movements and the stock figure drift apart. It also always
answers what the stock was consumed by.

From this, `service_consumable` lets the `done` transition post consumption
automatically, and margin is `unit_price_cents` minus the recipe's
`qty * last_purchase_price_cents`.

**Money is never a float.** All amounts are integer cents, EUR.

**All timestamps are stored UTC and rendered in `Europe/Bratislava`.** Storing
local time breaks twice a year on the DST change.

## 6. Screens

One number drives the design: closing a visit must be one tap.

- **Today** (phone home screen). Time, name, service. A red bar on the row of
  any client with an `alert`, before it is opened. A "walk-in" button opens an
  immediately `done` visit.
- **Close visit.** The booking already gives the service and the price, so the
  default path is a single "Done" button: it writes the item at the current
  price and posts consumption from the recipe. `+ product`, `+ note`,
  `+ photo` and price override sit below the button, not before it. Getting
  this wrong kills the system within two weeks.
- **Photo:** `<input type="file" accept="image/*" capture="environment">`.
  Native, opens the camera, needs no library.
- **Calendar (week).** Appointments in colour, Google busy blocks in grey,
  free slots highlighted. Tapping a free slot opens a new appointment. No
  drag-and-drop in v1: click to create, click to edit. Moving an appointment
  happens once a day, not ten times.
- **Client card.** The red `alert` banner first, then contact details and
  "last seen 6 weeks ago", then history: date, service, findings, photos.
  Search is a plain `LIKE` on the name; FTS5 is unnecessary at a few hundred
  clients.
- **Recall list.** Clients past their `usual_interval_days`, most overdue
  first. Its own menu entry, not a dashboard tile: this is the list that
  produces revenue.
- **Stock.** Products with computed quantity, anything under `min_stock`
  highlighted. Tap to record purchase, correction or waste.
- **Expenses.** List plus a new entry with the document photographed through
  the same native camera input.
- **Dashboard.** Per period: revenue, expenses, result; revenue by service;
  **margin by service**; no-show count. One chart, not five.
- **Settings.** Working hours, services and their recipes, Google connection
  (admin), users (admin).

Navigation: bottom bar on phone (Today / Calendar / Clients / More), sidebar on
laptop. The service worker caches the Today page and static assets, read-only.

## 7. Calendar and Google integration

**Free slot computation.** Busy is appointments (`planned` and `done`) union
`busy_block`. Free is the day's `working_hours` minus busy, sliced on a 15
minute grid, keeping only slots where the requested service duration fits.

**`buffer_min` is a required setting**: mandatory gap between clients for
disinfection and turnaround. Without it the system packs appointments back to
back, which is not how the work happens.

**Reading Google.** `freebusy.query` every 10 minutes for today plus 60 days,
replacing `busy_block` rows for that range. Scope `calendar.freebusy`: the
response contains busy intervals only, never event titles, attendees or
descriptions. The private calendar's contents are therefore never seen by this
app, which is the GDPR-preferable direction as well as the simpler one.

The obvious alternative, polling Google's "secret address in iCal format", was
rejected: Google refreshes that feed roughly once every 24 hours server-side
and it cannot be forced faster, so a slot could show as free for a day after
it was booked. Google's CalDAV interface implements every report except
`free-busy-query`, so CalDAV is not a route either.

**Writing to Google.** The integration is otherwise asymmetric: we see her
calendar, Google does not see the pedicure appointments, so she could
double-book herself from her phone. On create or change, the app writes a
neutral "Busy" event into a dedicated "Pedikur" Google calendar - date and
time only, no client name - and stores `google_event_id`. Client identity and
health data never reach Google. This needs a wider scope than reading
(`calendar.events` family); **the exact minimal write scope is unverified and
must be confirmed during implementation.**

**Staleness is shown, never hidden.** If Google is unreachable the last cache
is kept and labelled with its age ("Google calendar: refreshed 47 minutes
ago"). Stale busy data presented as current is what produces double bookings.
Failed writes set `google_sync_pending` and are retried by the next 10 minute
cycle.

OAuth consent is done once by the admin. The refresh token lives in `setting`,
the access token in memory.

## 8. Error handling

1. **Double tap on "Done"** would post consumption twice. The transition to
   `done` is idempotent: one transaction, and stock movements are written only
   if the appointment was not already `done`. This will happen in practice.
2. **Money is integer cents**, never float.
3. **Google outage**: cached busy blocks with a visible age, as above.
4. **Reverse proxy chain** (Pangolin -> newt -> app): without
   `--forwarded-allow-ips` and correct proxy-header handling, `Secure` cookies
   and redirects break. Verify when Pangolin is wired up.
5. Orphaned upload files after a failed insert are accepted; they cost bytes.

## 9. Testing

A small pytest suite covering four things, no framework ceremony, no
per-route tests:

- free slot computation, **including a case on the DST changeover Sunday**
- stock summation and the idempotent `done` transition
- margin calculation
- `freebusy` response handling from a mocked Google response

These are the places where a wrong number would appear silently.

## 10. Backup, restore and rollback

**A live WAL-mode SQLite database must not be copied with `cp`** - the result
is torn and opens only sometimes. Nightly cron uses the online backup:

```
sqlite3 /srv/docker-data/praxis/db.sqlite \
  ".backup /srv/docker-data/praxis/backup/db-$(date +%F).sqlite"
```

Seven daily copies are kept; the existing restic job then carries them along
with `media/`. Photos and scans are plain files and need nothing special.

**Restore is proven, not assumed.** Add praxis to `scripts/restore-test.sh`:
restore into a temp directory, run `PRAGMA integrity_check`, and count rows in
`client` and `appointment`.

**Rollback paths, written down before they are needed:**

- A bad deploy: redeploy the previous commit in Komodo. No data loss, because
  schema migrations stay forward-compatible.
- Corrupted data: stop the container, copy back the most recent nightly
  `.backup` file, start it. Loses at most one day of entries.

Both commands belong in the stack README; nobody invents them at night.

## 11. Deployment

Compose stack under `compose/proxmox-lxc-100/praxis/`, `restart:
unless-stopped`, volume `/srv/docker-data/praxis`, `TZ` from `.env`. Secrets
(`SECRET_KEY`, Google client id and secret) in the Komodo Stack Environment,
never in git. A `/health` endpoint with an Uptime Kuma monitor.

**Unverified:** how Komodo handles a `build:` directive in this git-based
setup. Fallback is a GitHub Actions build pushed to ghcr.io, the way the docs
site already builds in CI.

## 12. Phases

1. Auth, clients, appointments, closing a visit. Usable from here, and data
   starts accumulating.
2. Products, recipes, stock, expenses.
3. Google sync, free slot view.
4. Dashboard, recall list, MCP server.

## 13. Rejected alternatives

- **Paperless-ngx for the document side.** The original idea, dropped on
  volume: 30 to 60 purchase documents a year, roughly 250 over five years. OCR,
  tagging and full-text search pay off in the thousands, not the hundreds, and
  the amount is typed in anyway because the app calculates from it. It would
  also be a new stack with its own backup and auth, plus a link to maintain
  between expense row and document. Revisit if she cannot find a receipt by
  scrolling, or past roughly 500 documents; the MCP servers for it are not
  going anywhere.
- **Directus as the backend.** Recommended first, then dropped by the owner in
  favour of writing the backend. Worth recording why it was a close call and
  what the risk was: Directus v12 (released 2026-05-26, announced 2026-04-22)
  moved to the MSCL licence with an enforced free Core tier of 3 user seats,
  25 collections and 5 flows. Our shape fits comfortably, and the Open
  Innovation Grant (under USD 5M revenue and 50 employees) lifts the caps, but
  that is two licence changes in three years (BSL in 2023, MSCL in 2026) for a
  tool meant to run unattended for years.
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

## 14. Assumptions to confirm

- Interface language is Hungarian, single language, no i18n layer.
- Only the two accounts; no colleague also recording work.
- Products are consumed only for now, with retail sale planned later: both
  `stock_movement` reasons exist in the model from the start, but only the
  consumption UI is built.
- Hosted on LXC 100, not the K3s cluster, because the cluster is at a separate
  location and this is a daily-use tool.
