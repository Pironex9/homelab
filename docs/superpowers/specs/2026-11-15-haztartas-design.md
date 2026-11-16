# Haztartas: shared household budget - design

**Date:** 2026-11-15
**Status:** approved design (2026-11-15), written after a brainstorming session
and a builder check the same day. Implementation plan not yet written.
**Name:** `haztartas` - directory, container, database and URL

## 0. The document set

This spec is the hub. Plans are written one per phase, just in time, so each
argues from code that exists.

| Phase | Plan | Status |
|---|---|---|
| 1. Accounts, manual entry, categories and budgets, income, hidden entries, pocket money, monthly view, installable PWA with offline capture of the manual form | `docs/superpowers/plans/2026-11-15-haztartas-phase1.md` | written, not started |
| 2. Receipt photo (eKasa QR, then Gemini), voice entry (Gemini audio), offline queuing of photo and audio, attachments, Drafts screen | not written | |
| 3. Budget push notifications, month-over-month trends, Pedikur income draft | not written | |
| Later | Hungarian price lookup (GVH Arfigyelo), AI questions over the ledger | not planned | |

## 1. Context

A family of three - two adults and a teenager - wants one shared ledger of
household money: where it goes, and whether each category stays inside its
monthly limit. "What would this cost elsewhere" is a nice-to-have, not a goal.

Today nothing is tracked. The pitch that started this: photograph a receipt and
let it be read; say "six euros bread, cash" out loud right after paying and
have it recorded, transcript kept. Cash is the gap that bank-sync apps (YNAB,
Monarch) cannot see, and voice is how the voice-first apps fill it.

The family shops in Slovakia and often in Hungary, occasionally elsewhere.
Amounts arrive in EUR and HUF, rarely another currency.

### Why built, not adopted (researched 2026-11-15)

No existing product combines receipt reading, voice entry, a shared household
ledger and self-hosting:

- Finvo (Flutter + FastAPI): voice and family spaces, no receipt reading,
  56 stars, no releases.
- Receipt Wrangler: receipts and households, no voice, not a budget tool.
- ezBookkeeping: receipt AI and a PWA, no multi-user mentioned.
- SpendSpentSpent: households, AI only for category suggestions.
- Monairo, moneasy: voice and family sharing, but closed and hosted.
- Firefly III / Actual Budget as a backend: the hidden-entry rule and the
  child role would have to be built against their permission models.

**Every expense goes in, not only cash and receipts** (decided in the grilling
pass): fixed bills and subscriptions as recurring items (section 4), receipts by
photo, receipt-less card spending (online orders, small card payments) by voice
or by hand. Once a month the adults compare the month against the bank statement
by eye. A bank CSV import would automate that; it waits on the "later" list
until the by-eye check proves to find a lot.

### What this is not

- Not bank sync. Every entry is captured by a person.
- Not a bill splitter. Nobody owes anybody; it is one household's books.
- Not bookkeeping or tax.

## 2. Users, roles and visibility

Two roles, one column on the user row: `adult` or `child`. Three accounts at
launch (two adults, one child). Created by CLI, no sign-up page.

| | adult | child |
|---|---|---|
| Record a household entry (manual, voice, photo) | yes | yes |
| See household entries | all | only the ones they created |
| Hide an entry | yes | yes |
| Income, monthly balance, budgets | yes | no |
| Pocket money wallet | sees it, item by item | their own |
| Manage categories, budgets, recurring income | yes | no |

**Hidden entry.** Any entry can be marked hidden by its author. Others see only
amount, category, date and author, never merchant, note, line items,
transcript or photo. It is real spending, so it counts in totals and budgets
from the day it is recorded. Optional `reveal_on` date: from that day it is an
ordinary entry. The author can reveal it any time. Built for gifts, but the
rule does not care why.

```
Ajandek            ████████░░  82 / 100 EUR
  Rejtett tetel       45 EUR   (author, nov. 12.)
```

**The one visibility rule, written once in the service layer.** A viewer sees
an entry in full if they authored it, or it is not hidden (or `reveal_on` has
passed) and their role allows its wallet. Otherwise an adult sees the redacted
form; a child sees nothing. Every list, report, export, photo and audio URL
goes through it. A hidden entry's photo or audio file must 404 for anyone but
its author, not just be left out of the page.

**Changing entries.** Reading is one rule; changing is a second, also written
once in the service layer:

- The author can edit, delete and reveal their own entries.
- An adult can edit or delete any **non-hidden** entry, the other adult's and
  the child's included: the family fixes each other's typos.
- A hidden entry can be changed only by its author. Nobody else gets an edit
  screen for it, so no edit path can leak its fields.
- Either adult can confirm or correct a recurring draft (a salary draft is not
  private to its owner; income is adult-visible anyway).
- The child changes only their own entries.
- Delete is soft (`deleted_at`), as in Pedikur. Deleted entries leave every
  total; restore is by SQL in phase 1, no UI.

**Pocket money.** The child has one wallet with a balance. A parent's top-up is
one action that writes two linked entries: an expense in the household wallet
(category "Zsebpenz") and an income in the child's wallet. The child records
spending from the wallet like any other entry; parents see it item by item.
The child may also record income into their own wallet only (gift money,
earnings); at launch an adult records an opening-balance income there. Nothing
in the child's wallet ever counts in household totals or budgets: the top-up
expense already did, and gift money was never household money.

## 3. Capture

All capture paths end on the same **confirm screen**: date, merchant, amount,
currency, category (or per-line categories), wallet, cash/card, hidden toggle.
Nothing is saved as confirmed without a person pressing save.

### 3.1 Manual

The confirm screen, empty.

### 3.2 Receipt photo (phase 2)

Taken with `<input type="file" accept="image/*" capture="environment">` -
the phone's own camera app, no camera library.

1. **eKasa QR first (Slovak receipts).** Scan the photo with Chrome's
   `BarcodeDetector`. If a QR is found, the server POSTs its text as
   `{"receiptId": ...}` to
   `https://ekasa.financnasprava.sk/mdu/api/v1/opd/receipt/find`.
   Undocumented ("Over doklad" backend), rate limited: sequential calls,
   retry after 1 s and 3 s, 10 s timeout. Verified 2026-11-15 to answer HTTP
   200 JSON with `returnValue: 0` and `receipt: null` for a well-formed
   unknown ID. **The item field names of a real response are not yet seen** -
   the phase 2 plan starts by capturing one real receipt's JSON as a test
   fixture. Not found or unreachable falls through to step 2.
2. **Gemini on the photo** (everything else: Hungarian, other countries,
   hand-written, invoices, price tags). Structured output against a fixed
   JSON schema: merchant, date, currency, total, lines (name, quantity, unit
   price, line total, suggested category from the household's category list).
3. **Confirm screen**, prefilled. If line totals do not sum to the total,
   the screen says so rather than silently picking one.

Line items are stored (`entry_line`) because a Tesco receipt holds food and
detergent; budgets count lines by their own category, and an entry without
lines by the entry's category.

**A 40-line receipt is confirmed at a glance.** Gemini suggests a category per
line; the confirm screen shows category subtotals, each expandable to its
lines, and a line can be moved to another category:

```
Tesco, nov. 15.                 84,30 EUR
  Elelmiszer      31 tetel      71,40   >
  Haztartas        4 tetel       9,90   >
  Higienia         2 tetel       3,00   >
                               [ Mentes ]
```

**Corrections are remembered.** Moving a line stores `(merchant, normalised
line name) -> category` in a `line_category_rule` table; from then on that pair
takes the rule, not Gemini's guess.

**Receipt photos are kept forever** and double as the warranty copy (thermal
paper fades in 1-2 years; EU warranty is 2 years). Entry search covers merchant
and line names, so "mosogep" finds the receipt and its photo. No warranty
expiry tracking.

**Hungarian receipts have no lookup path today.** The NAV eNyugta customer app
can fetch e-receipts from new e-cash registers by QR, but third-party access is
unverified, and old online cash registers (most chains) may run until
2028-07-01. Revisit when the eNyugta export format or customer-app interface
is documented.

### 3.3 Voice (phase 2)

`MediaRecorder` records audio in the browser. The audio file goes to Gemini,
which returns transcript plus the same structured fields as the photo path in
one call. The transcript is stored on the entry. No Web Speech API: it needs a
network round trip to Google at the moment of speaking, which breaks offline
capture.

### 3.4 Offline capture

Shops have bad signal. The capture screen works offline. Phase 1 queues the
manual form only; phase 2 adds photo and audio to the same queue. The queue
item format carries a `kind` and an optional binary slot from phase 1, so
phase 2 extends it rather than migrating it.

- A service worker caches the capture shell (HTML, CSS, JS).
- A capture made offline (photo, audio, or a manual form) is stored in
  IndexedDB as a pending item and uploaded when the network returns
  (`online` event plus a retry on app open). Photo and voice items then run
  through extraction and wait as **drafts** to be confirmed.
- **A visible counter** - "3 tetel var feltoltesre" - on every screen while
  the queue is non-empty. Browser storage is less durable than a native
  database; a lost item must not go unnoticed.
- The app requests `navigator.storage.persist()` on first run.
- Each pending item carries a client-generated UUID; the server treats a
  repeated UUID as the same upload (idempotent), so a retry after a lost
  response never duplicates an entry.

Everything except capture (reports, budgets, editing) needs the network and
says so plainly when it is missing.

### 3.5 Duplicates

Three people on three capture paths will record the same purchase twice (voice
at the till, the receipt photographed that evening). Before saving, the confirm
screen looks for a likely duplicate: same wallet, same day or the day before,
amount within 2%. If found: "Lehet, hogy ez mar rogzitve van: 32,00 EUR, Lidl,
<author>, hangos, 17:40" with three choices:

- **Merge** - the existing entry takes the new one's lines, photo and amount
  (receipt data is the more exact).
- **Save separately** - two real coffees on one day exist.
- **Cancel.**

Never automatic. A hidden entry is never offered for merging and the warning
reveals nothing beyond what the redacted form already shows ("egy rejtett tetel
hasonlo osszeggel").

### 3.6 Business purchases

Pedicure supplies are recorded only in Pedikur; the household gets the business
result instead (section 4). The confirm screen has no business flag beyond a
reminder in the category list ("Pedikur anyag -> a Pedikur appba").

## 4. Money

- Amounts are integers in minor units (cents, filler). No floats.
- Each entry keeps its original amount and currency, plus the EUR amount and
  the rate used, fixed at save time for the entry's date.
- Rates: ECB daily reference rates (`eurofxref-daily.xml`), fetched once a day
  by an in-process task into an `fx_rate` table. Weekend or holiday dates use
  the latest earlier rate. A currency the ECB does not publish is entered with
  a manual rate on the confirm screen.
- Reports and budgets are in EUR.
- **ECB rate only, no "amount actually charged" override** (owner's decision):
  a Hungarian card payment's bank-side EUR differs by the bank's spread and
  fees, and that difference is accepted rather than modelled.
- **Months are calendar months**, matching the bank statement. Two salaries on
  different days make any pay cycle arbitrary. Next to the balance, one line of
  expected income from pending recurring items ("+2 fizetes varhato 10-en es
  15-en") keeps the early-month balance from reading as overspending.

### Income

Adults record income (salary, other). Salary is a **recurring item**: on its
day each month a draft income entry is created with the usual amount, for the
adult to confirm or correct (net pay varies). Same mechanism for any other
recurring item later (rent, subscriptions) without new code.

### Pedikur income (phase 3)

The Pedikur app runs on the same LXC with an internal, token-protected `/api/*`
(Pangolin-blocked). On the 1st of each month a draft income entry is created
for the previous month: **Pedikur revenue minus Pedikur expenses**, not revenue,
because supplies are already paid out of it. Social and health contributions
and tax are paid from household money and are household recurring expenses.
Pedikur's API exposes visits today but no expenses, so phase 3 adds one small
read-only endpoint there (monthly expense sum). Revenue is summed from closed
visits the way Pedikur's own dashboard will define it; the phase 3 plan reads
Pedikur's code for that definition rather than re-deriving it.

### Budgets

One monthly limit per category, in EUR, set by adults. The monthly view shows
spent / limit per category and the household balance (income minus expense).
Phase 3 adds Web Push to both adults at 80% and 100% of a category.

`ponytail:` the limit is a column on `category`, so changing it rewrites how
past months look. A `budget(category, valid_from, amount)` table is the
upgrade if anyone wants history to keep the old limits.

## 5. Architecture

Same shape as Pedikur (FastAPI + SQLite + server-rendered Jinja/htmx, one
container on LXC 100, Komodo deploy). The one addition is a small client-side
part for offline capture, which server-rendered pages cannot do.

```
compose/proxmox-lxc-100/haztartas/
  docker-compose.yml
  app/
    main.py          FastAPI: HTML routes + JSON routes used by the capture JS
    services/        business logic; visibility rule lives here, once
    extract/         ekasa.py, gemini.py (photo + audio -> draft)
    fx.py            ECB fetch, in-process daily task
    recurring.py     draft creation, in-process daily task
    backup.py        nightly Connection.backup()
    cli.py           create-user, reset-password
    migrations/      numbered .sql, applied at startup
    strings/hu.py    all user-facing text, keyed
    templates/
    static/          htmx 2.x, CSS, capture.js, sw.js, manifest.webmanifest
volume: /srv/docker-data/haztartas/{db.sqlite, media/, backup/}
```

- **SQLite in WAL mode.** Three users, a few thousand entries a year.
- **No npm, no bundler.** `capture.js` and `sw.js` are hand-written vanilla JS;
  IndexedDB through its plain API.
- **Gemini key** in the Komodo Stack Environment. The model is a current
  Flash-class model chosen at plan time; extraction prompts and JSON schemas
  live in `extract/`, versioned with the code.
- **Gemini data terms:** in the EEA the paid-service data terms apply to free
  quota as well (Gemini API Additional Terms), so receipts are not used for
  training. Re-check at plan time; terms change.

### Data model (sketch, the plan finalises it)

- `user(id, name, role, password_hash, failed_logins, locked_until)`
- `wallet(id, name, owner_user_id NULL)` - NULL owner = household
- `category(id, name, kind expense|income, monthly_limit_eur_minor NULL, archived)`
- `entry(id, client_uuid UNIQUE, wallet_id, kind expense|income, status draft|confirmed, date, merchant, amount_minor, currency, eur_minor, fx_rate, category_id NULL, payment cash|card|other, note, hidden, reveal_on NULL, source manual|voice|photo|ekasa|recurring, transcript, created_by, transfer_group NULL, recurring_id NULL)`
- `entry_line(id, entry_id, name, quantity, unit_price_minor, total_minor, category_id)`
- `attachment(id, entry_id, kind photo|audio, path, raw_json)` - eKasa or Gemini raw response kept for debugging and re-extraction
- `recurring(id, wallet_id, category_id, name, amount_minor, currency, day_of_month, owner_user_id)`
- `fx_rate(date, currency, rate)`

## 6. Access and security

**Reachable from the internet through Pangolin; no Tailscale on the phones**
(owner's decision). This puts household finances, receipt photos and a
teenager's spending on a public URL, so:

- **The app never trusts that it sits behind Pangolin.** Own login, Argon2id
  (`argon2-cffi`), 15-minute lock after 5 failures, as in Pedikur.
- **Session:** signed cookie, `HttpOnly`, `Secure`, `SameSite=Lax`, 90-day
  rolling expiry. A family will not tolerate logging in weekly; a stolen phone
  is handled by rotating `SECRET_KEY` (logs everyone out) or resetting that
  user's password via CLI.
- **Pangolin rules:** SSO bypass for SK and HU (Pangolin's own SSO in front of
  a service worker turns background uploads into login-page redirects that
  fail silently), Pangolin SSO for every other country. Abroad, the offline
  queue simply waits. Unverified guess: EU roaming is usually home-routed, so
  a Slovak SIM abroad may still appear as SK.
- **No separate `/api/*` surface** and no bearer token: the JSON routes are
  same-origin, session-authenticated, and exist only for the capture JS. No
  MCP server is planned; add one later the Pedikur way (internal network,
  token, Pangolin-blocked path).
- **Photos are resized in the browser** (canvas, longest side about 1600 px,
  JPEG) before queuing: a phone photo of 3-5 MB becomes a few hundred KB,
  which keeps IndexedDB and the LXC 100 rootfs (the pve/data thin pool) small.
  Unverified estimate: well under 1 GB a year at a few receipts a day.
- **Uploads:** size cap, image/audio MIME check, files stored under random
  names outside the static root, served only through the visibility rule.
- **Public docs** use a placeholder domain, not the real subdomain.

## 7. Interface

Hungarian, mobile-first, one-handed. Designed with the `impeccable` skill and
checked with the headless Chrome screenshot loop, screen by screen, before the
owner sees it. Own small token set, not `brand/` (this is the family's tool, not
the portfolio's).

Screens (layout decided during implementation with `impeccable`):

1. **Home / month** - balance (adults), categories with spent/limit bars,
   pending-upload counter, three big capture buttons: photo, voice, manual.
2. **Confirm** - the shared screen from section 3.
3. **Entries** - month list, filter by wallet / category / author.
4. **Drafts** - extracted or recurring items waiting for confirmation.
5. **Pocket money** - child: balance and own entries; adult: same plus top-up.
6. **Settings** (adults) - categories and limits, recurring items, users.

## 8. Error handling

- Extraction failure (Gemini error, unreadable photo): the item becomes a
  draft with the photo attached and empty fields, never lost.
- eKasa unreachable or rate limited: fall through to Gemini, record which path
  produced the draft in `source`.
- FX fetch failure: keep the last rate, log it; the confirm screen shows the
  rate it used.

## 9. Testing

pytest on the places where a wrong answer is silent:

- the visibility rule: every role x hidden x reveal_on x wallet combination,
  including the photo/audio file routes
- budget sums: line-level categories, hidden entries counted, the child's
  wallet not double-counted after a top-up
- FX: weekend dates, missing currency, minor-unit rounding
- idempotent upload: the same `client_uuid` twice yields one entry
- eKasa and Gemini parsing against saved real responses (fixtures)

The offline queue is tested by hand on a phone in flight mode, with the steps
written in the phase 1 plan.

## 10. Backup and deployment

As Pedikur: nightly `Connection.backup()` into `backup/`, seven copies. Off the
container, `/srv/docker-data` is carried only by the 02:00 vzdump of LXC 100
(`scripts/README.md`); the pve restic job covers the host root, not this, and
`scripts/restore-test.sh` discovers restic repositories rather than listing
services, so there is no per-service hook to add.

**No offsite copy in phase 1, by the owner's decision (2026-11-15)**, the same
level Pedikur runs at: a fire or theft at home takes the data and its backup
together. Losing budget history is annoying, not irreplaceable. The fix is a
separate task covering both apps at once: an encrypted restic job sending
`/srv/docker-data/{pedikur,haztartas}/backup/` (and `media/`) to the Hetzner
VPS, with its own restore check.
Komodo stack on LXC 100, port 3011 (verify free on the host at plan time).

## 11. Approaches considered

| Approach | Trade-off | Outcome |
|---|---|---|
| **PWA on the Pedikur stack** | One codebase, instant updates, screenshot-verifiable UI, `impeccable` applies directly; offline storage less durable than native | **Chosen** by the owner |
| Native Kotlin + Compose app, same backend | Most robust offline and background sync; APK releases to three phones, UI only verifiable in an emulator, roughly double the code | Rejected |
| Fork Finvo | Voice and family spaces exist; immature, no receipts, a different permission model | Rejected |
| Firefly III / Actual as backend | Mature ledger; hidden entries and child role fight their models | Rejected |

Network: Tailscale on all phones was recommended for keeping the data off the
internet; the owner ruled it out, hence section 6.

## 12. Left to the builder

- Gemini model id and prompt wording, schema field names
- exact table and column names, indexes
- screen layouts (with `impeccable`)
- the default category list (Hungarian names; adults can edit)
