**Date:** 2026-11-16
**Host:** LXC 100 docker-host (192.168.0.110), port 3011
**Public route:** `https://your-budget.yourdomain.com` via Pangolin (Hetzner VPS)

---

# A Family Budget App, and What a Review Gate on Every Task Caught

The second application written here rather than deployed. A shared household ledger for a
family of two adults and a teenager: record every expense in a few seconds, by hand and
offline if the shop has no signal, see where the month's money went as a map of tiles,
keep each category inside a monthly limit, and hide a gift from the rest of the family
while its amount still counts.

**325 tests, twelve tasks, about fifty review findings acted on, one Playwright script that
proves the offline queue without a phone.** Every task was implemented by a fresh subagent
and reviewed by another fresh subagent before the next one started; the whole branch then
had one more review on the most capable model. This page is mostly about what those
reviews found, because nearly every finding generalises.

---

## What it does in phase 1

| | |
|---|---|
| Capture | a short form (amount first, then category, where, date); works offline and queues |
| Month view | balance sentence, a tile map of spending by category with a limit rail per tile, who spent how much |
| Income | salaries as recurring items that become a draft on their day, confirmed by an adult |
| Roles | two adults, one child; the child sees only their own entries and their pocket money wallet |
| Hidden entries | others see amount, category, date and author only, until an optional reveal date |
| Currencies | EUR and HUF (and other ECB currencies); every entry keeps its original amount, the EUR value is fixed at save time from the ECB daily reference rate |
| Install | a PWA: installable from Chrome on Android, own icon, own window |

Phase 2 (receipt photos and voice) is designed but not built: Slovak receipts carry an
eKasa QR code, and the tax authority's undocumented "Over doklad" backend
(`POST https://ekasa.financnasprava.sk/mdu/api/v1/opd/receipt/find` with
`{"receiptId": "O-..."}`) returns the receipt; everything else goes to an LLM.

---

## The stack

Same shape as the [Pedicure Practice App](46_Pedicure_Practice_App.md): Python 3.13,
FastAPI, SQLite in WAL mode, server-rendered Jinja with htmx, numbered SQL migrations, one
container, no build step. Money is integer minor units everywhere. The one addition is
about 460 lines of hand-written JavaScript for the offline capture queue (`capture.js`,
`sw.js`), because a server-rendered page cannot save a form with no network.

The visual direction was chosen by the owner from mockups shown side by side in a browser
companion page: five "worlds" in the first round (all rejected), four in the second, and
the tile map won. A design skill (`impeccable`) then built the foundation, a fresh
reviewer critiqued the screenshots, and a documenter wrote the design system down from the
built CSS rather than from intentions.

---

## The privacy boundary, and the four ways it almost leaked

All visibility lives in one module: a Python function that decides "full", "redacted" or
"none" for one entry, and its SQL twin used by every list and search. Every route goes
through it. That was the plan. These are the ways it still leaked during the build, each
caught by a review before deployment.

### 1. A SQL filter that fails open without a join

The child's filter read `Wallet.owner_user_id` directly. Every caller wrote
`select(Entry).join(Wallet).where(listable(...))`, and the tests passed. A reviewer wrote
the one query nobody had: the same filter without the join. SQLAlchemy then builds a
cartesian product, the condition holds for every entry paired with the child's wallet
row, and an adult's household entry came back to the child. The only signal was a
SAWarning.

**Fix:** `Entry.wallet_id.in_(select(Wallet.id).where(Wallet.owner_user_id == viewer.id))`,
which is correct with or without a join, plus a test that compares both. A privacy filter
must not depend on how the caller happened to build the rest of the query.

### 2. A duplicate warning that said more than the redacted row

Before saving, the app looks for a likely duplicate (same day or the day before, within
2%). For a hidden entry the hint nulled the merchant, as specified, but still carried the
exact `created_at`. The redacted list row shows the date, not the minute. For a gift, the
minute is information. The plan had specified the hint's shape; the spec said "reveals
nothing beyond the redacted form". The spec won.

### 3. An edit form that silently moved a child's entry

Adults may fix the child's typos. The edit form offered adults only the household wallet,
so the wallet `<select>` had no option for the entry's own wallet, and a browser submits
the first option of a select whose value matches nothing. One typo fix moved the child's
spending into the household totals, with a 303 and no warning. The service allowed it,
because an adult may add expenses to the household.

**The general lesson:** a server-rendered form round-trips every field. If the form cannot
represent the current value, the save rewrites it.

### 4. A second route that skipped the module

The drafts screen (recurring salaries waiting for confirmation) listed rows with its own
query. An author can hide their own draft, and the other adult then saw the merchant and
note in full on `/drafts`, and could open a pre-filled form. Everything else went through
the visibility module; this one route did not, because it was "only drafts".

---

## Money that looked right

- **`"0.500"` parsed as 500.00.** The rule "a dot followed by exactly three digits is a
  thousands separator" accepted a leading zero group. Half a euro became five hundred.
  Fixed by requiring the first group to start with 1-9.
- **`"12 50"` parsed as 1250.00**, because spaces were thousands separators anywhere. A
  space may now only separate groups of exactly three digits. The non-breaking spaces a
  Hungarian keyboard or a copy-paste produces are normalised first, so `1 200` still works.
- **HUF dropped its decimals when they were not zero:** 120,50 Ft was stored and converted
  correctly but displayed as "120 Ft". A shown number that differs from the stored one is
  a wrong number.
- **A secret gift in the child's wallet moved the child's balance** by an amount the child
  cannot see. The balance now counts only what the viewer may list, so the adult and the
  child see different balances until the reveal date, which is the point.

---

## The offline queue, and the one rule that matters

A capture made offline goes into IndexedDB with a client-generated UUID and is uploaded
when the network returns; the server treats a repeated UUID as the same entry. The rule
that keeps it honest: **an item leaves the phone only on a 2xx JSON response that echoes
its UUID.** Everything else keeps it, and these are the shapes "everything else" turned
out to include:

| Response | Where it comes from | What the queue does |
|---|---|---|
| network error, timeout | no signal, captive Wi-Fi | keeps it, retries every 15 s and on `online` |
| `opaqueredirect` (302) | Pangolin's SSO wall abroad | keeps it, shows "log in to upload" |
| `200 text/html` | a login page served in place of the API | keeps it, shows "log in to upload" |
| `401` JSON | expired session | keeps it, shows "log in to upload" |
| `409` | the item belongs to another user on the same phone | keeps it, refuses to upload it as the current user |
| `422` | bad amount, missing rate | keeps it, puts it back into the form to fix |

Captive Wi-Fi with no internet never fires an `online` event when it comes back, which is
why the timer exists. Two smaller rules came from reviews: refused items are not retried by
the timer (only on load and `online`), and a service worker fetch uses `cache: 'no-cache'`
so a deploy actually reaches phones that already have the app.

**The shared phone.** Each queued item records which user filled the form. If a different
user logs in on the same phone, the server answers 409 rather than saving the first
person's (possibly hidden) items under the second person's name, and the screen shows only
a count of such items, never their content.

**Proving it without a phone.** `scripts/offline_check.mjs` drives headless Chrome through
Playwright: log in, open the capture page once so the service worker caches it, set the
browser context offline, record two entries, assert the counter shows 2, go online, wait,
and assert both entries exist exactly once on the server. It also replays the Pangolin
shapes from the table with `page.route()`. Forty-one steps, run on a fresh database.

One trap worth recording: Playwright's `waitForFunction` treats a returned Promise as a
truthy value and returns immediately. Two early checks that awaited an IndexedDB count
inside it never tested anything; they passed against a broken queue.

---

## Smaller things that were wrong

- **Archiving a category stopped recurring drafts silently.** A salary on an archived
  category failed validation every hour and was logged and skipped; the settings page still
  showed it as active. Archiving is now refused while an active recurring item uses the
  category.
- **A password reset did not end other sessions.** The session cookie held only the user
  id, and a 90-day rolling session on a stolen phone survived the reset. The session now
  carries a short SHA-256 fingerprint of the password hash.
- **CSRF on a public app sharing a registrable domain.** `SameSite=Lax` stops cross-site
  POSTs, not same-site siblings on other subdomains. A small middleware rejects unsafe
  methods whose `Origin` does not match `Host` (or `X-Forwarded-Host`). Behind Pangolin it
  was verified from outside: a same-origin POST passes, a foreign `Origin` gets `403`.
- **The restore instructions were wrong, measured.** The README said a leftover
  `db.sqlite-wal` "whose salt no longer matches is discarded". It is not: copying a
  one-row backup over a live file with a stale WAL beside it produced 199 rows and a table
  the backup did not contain. Restore is now stop, `rm -f db.sqlite-wal db.sqlite-shm`,
  copy, start. The Pedicure app's README carried the same claim and was corrected too.
- **The stack count was wrong twice.** Counting `docker-compose.yml` files missed two stacks
  that use `compose.yaml`. The landing page's build script counts all three spellings, which
  is why its number was right.

---

## How the work was split

A brainstorm, a grilling session, a written spec and a plan with twelve tasks came first.
Then, per task: a fresh implementer subagent given only the task's text, a fresh reviewer
given the diff, the task and the spec, and a fix loop when the reviewer found something.
Screens were not delegated: a subagent cannot see what it rendered, so the templates and
CSS were done in the main session with a screenshot loop at 390 and 360 px.

What each layer caught, roughly:

| Layer | Caught |
|---|---|
| Tests written first | the logic each task was asked for |
| Per-task review | most privacy and money defects above, the offline-queue edge cases |
| Screenshots | clipped accents on tiles, a hidden-entry note squeezed to nothing, a radio group that made the form 650 px wide |
| Whole-branch review | defects between tasks: an orphaned draft no role could see, the password reset, the shared-phone leak, the WAL restore |
| Real deploy | nothing new this time; the Pedicure lessons (Komodo rebuild, Pangolin rule order, fresh DNS) were applied up front |

---

## Known and not fixed

- Only currencies the ECB publishes can be chosen in the form.
- The pocket money screen lists 50 rows per wallet and links to the full list beyond that.
- No offsite copy of the database: the in-app nightly snapshots and the 02:00 vzdump of
  LXC 100 live on the same machine. Accepted for phase 1; a restic job to the VPS for this
  app and the Pedicure app is planned.
- Synchronous SQLite calls inside async handlers; fine for three users.
