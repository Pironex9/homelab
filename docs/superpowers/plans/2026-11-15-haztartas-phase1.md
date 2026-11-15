# Haztartas Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployed, installable household-budget PWA for three users: manual entry (also offline), categories with monthly limits, income with recurring drafts, hidden entries, a child role with a pocket money wallet, and the monthly view.

**Architecture:** A copy of Pedikur's shape: one FastAPI container, SQLite in WAL mode, server-rendered Jinja + htmx, numbered SQL migrations, in-process asyncio tasks. The only client-side code is the offline capture queue (`capture.js` + `sw.js`, IndexedDB). Visibility and edit permissions are two functions in one service module that every route goes through.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Jinja2, htmx 2.x (vendored), argon2-cffi, httpx (ECB fetch, already a test dependency), pytest. Vanilla JS, no build step.

**Spec:** `docs/superpowers/specs/2026-11-15-haztartas-design.md`

## Execution mode

Same as Pedikur, for the same reasons (its phase 1 plan, "Execution mode"):
**every task is implemented inline, and every task's Python + SQL diff gets a
fresh review subagent** given exactly three things: `git show` of the task, this
task's section of this plan, and the spec. Tasks build on each other (rules,
then services, then routes), which is the shape not to hand to parallel
implementers; the review is where a fresh context pays.

**Screens (Tasks 8-11) are never delegated** and run the screenshot loop:
render, screenshot, look, fix CSS, repeat. Recipe and its three load-bearing
settings: `compose/proxmox-lxc-100/pedikur/scripts/shot.mjs` and the memory
note on dashboard screenshots. UI skill: **`impeccable`**. Review subagents
are scoped to Python and SQL; appearance is not judged from a diff.

**One checkpoint: after Task 8** (design foundation), put the screenshots in
front of the owner and wait for a yes. Between other tasks keep going; stop
only for a blocker, a step in this plan that turns out wrong, or anything
destructive or outward-facing (the deploy in Task 12 is outward-facing).

## Global Constraints

- Directory `compose/proxmox-lxc-100/haztartas/`, container and DB name `haztartas`, **host port 3011** (verified free on LXC 100 with `ss -ltn`, 2026-11-15).
- Env prefix `HAZTARTAS_`: `HAZTARTAS_DATA` (default `/data`), `HAZTARTAS_SECRET_KEY` (required, non-empty), `HAZTARTAS_HTTPS_ONLY` (default `1`). No API token in phase 1.
- Same pinned `requirements.txt` as Pedikur; nothing added.
- **Money is integer minor units: hundredths of the entry's currency, every currency** (EUR cents, HUF filler). Columns end in `_minor`. Never float. FX rates are `Decimal`, stored as TEXT.
- `eur_minor` and `fx_rate` are fixed on the entry at save time and recomputed only when amount, currency or date changes.
- **Dates of entries are local calendar dates** `YYYY-MM-DD` in `Europe/Bratislava`; audit timestamps are UTC ISO-8601. "Today" always comes from `app.clock.today()`, never `date.today()`.
- Months are calendar months, `YYYY-MM`.
- Soft delete via `deleted_at`; nothing hard-deletes. Drafts and deleted entries are in no total.
- **The child's wallet is in no household total or budget.** Household totals read only the household wallet (`owner_user_id IS NULL`).
- Session cookie: `HttpOnly`, `Secure` (unless `HAZTARTAS_HTTPS_ONLY=0`), `SameSite=Lax`, `max_age = 90 * 24 * 60 * 60`, re-issued on every response (Starlette 0.52.1 `SessionMiddleware` does this whenever the session is non-empty: verified in its source).
- The app never trusts Pangolin: own login, Argon2id, lock 15 minutes after 5 failures (Pedikur's `security.py` as is).
- All user-facing text in `app/strings/hu.py`. Everything committed is English. No em dashes anywhere.
- Copy, do not import, Pedikur's modules: the two apps deploy independently.

## Review Focus

1. **The offline queue meets an expired session or a Pangolin login redirect** (abroad): the item must stay queued and the counter must keep showing it. Server side `POST /capture/sync` without a session answers `401` JSON, never a `303` (Task 11 test `test_sync_without_session_is_401_json`); client side an item leaves IndexedDB only on a 2xx JSON response echoing its `client_uuid` (Task 11 phone test, step "flight mode and logout").
2. **The same capture uploaded twice** (retry after a lost response, two tabs): one entry. Task 5 `test_create_is_idempotent_on_client_uuid`, Task 11 `test_sync_twice_one_entry`.
3. **Search finds a hidden entry by its merchant or note** and so reveals what the gift was. Task 4 `test_search_never_matches_others_hidden_text`.
4. **Amounts typed the way people type them** ("12,5", "12.50", "1 200", "1.200,50", "", "abc", "-3"): parse or a form error, never a 500 and never a silently wrong number. Task 3 `test_parse_amount_*`.
5. **Late evening and month edges:** an entry saved at 23:30 local on the 31st belongs to that month; the form's default date is the local date; a recurring item on day 31 lands on 28/29/30 in short months. Task 1 `test_today_is_local`, Task 3 `test_scheduled_day_clamps`.

---

## File Structure

```
compose/proxmox-lxc-100/haztartas/
  Dockerfile, docker-compose.yml, .env.example, .dockerignore, requirements.txt   (from Pedikur, renamed)
  README.md                      run, Pangolin rules, password reset, backup, restore, rollback
  app/
    config.py db.py migrate.py backup.py security.py   (copied from Pedikur; security gains roles)
    clock.py                     today(), now_utc(), scheduled_day()
    money.py                     parse_amount(), fmt_money()
    fx.py                        ECB parse/store/lookup, daily task
    models.py
    cli.py                       create-user --role, reset-password
    main.py                      app, middleware, lifespan tasks, /sw.js, /manifest.webmanifest, /health
    migrations/001_schema.sql 002_seed.sql
    services/visibility.py       view_of(), can_edit(), entry filters
    services/entries.py          create/update/delete/reveal, duplicates, top-up
    services/summary.py          month summary, wallet balance
    services/recurring.py        drafts from recurring items, daily task
    routers/auth.py home.py entries.py drafts.py pocket.py settings.py capture.py
    strings/hu.py
    templates/  static/ (tokens.css app.css htmx.min.js capture.js sw.js manifest.webmanifest icons)
  scripts/shot.mjs               (copied from Pedikur)
  tests/
```

---

### Task 1: Stack skeleton, schema and seed

**Files:**
- Create: everything under "copied from Pedikur" above, `app/clock.py`, `app/models.py`, `app/migrations/001_schema.sql`, `app/migrations/002_seed.sql`, `app/main.py` (health only), `tests/conftest.py`, `tests/test_migrate.py`, `tests/test_backup.py`, `tests/test_config.py` (copied and renamed)

**Interfaces:**
- Produces: `config.load() -> Settings` (fields `data_dir, secret_key, https_only`; properties `db_path, media_dir, backup_dir`); `Database(db_path).session()`; `db.fold()`; `clock.today() -> str`, `clock.now_utc() -> str`; ORM classes `User, Wallet, Category, Entry, Recurring, FxRate` mirroring the SQL below.

- [ ] **Step 1: Copy** `config.py db.py migrate.py backup.py` and their tests from `compose/proxmox-lxc-100/pedikur/`; rename env vars to `HAZTARTAS_*`; drop `api_token` and its test. Copy `Dockerfile` (user `haztartas`), `docker-compose.yml` (service/container `haztartas`, `3011:8000`, no API token line, keep every load-bearing comment), `.env.example`, `.dockerignore`, `requirements.txt`, `scripts/shot.mjs`.

- [ ] **Step 2: Write `001_schema.sql`** (schema of record; models mirror it):

```sql
CREATE TABLE user (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('adult','child')),
  password_hash TEXT NOT NULL, failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT);
CREATE TABLE wallet (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL,
  owner_user_id INTEGER UNIQUE REFERENCES user(id));          -- NULL = household
CREATE TABLE category (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('expense','income')),
  monthly_limit_eur_minor INTEGER, sort INTEGER NOT NULL DEFAULT 0, archived_at TEXT);
CREATE TABLE recurring (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('expense','income')),
  category_id INTEGER NOT NULL REFERENCES category(id),
  amount_minor INTEGER NOT NULL, currency TEXT NOT NULL,
  day_of_month INTEGER NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
  owner_user_id INTEGER REFERENCES user(id), archived_at TEXT);
CREATE TABLE entry (
  id INTEGER PRIMARY KEY, client_uuid TEXT UNIQUE,
  wallet_id INTEGER NOT NULL REFERENCES wallet(id),
  kind TEXT NOT NULL CHECK (kind IN ('expense','income')),
  status TEXT NOT NULL CHECK (status IN ('draft','confirmed')),
  date TEXT NOT NULL, merchant TEXT, note TEXT,
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0), currency TEXT NOT NULL,
  eur_minor INTEGER NOT NULL, fx_rate TEXT NOT NULL,
  category_id INTEGER REFERENCES category(id),
  payment TEXT NOT NULL CHECK (payment IN ('cash','card','other')),
  hidden INTEGER NOT NULL DEFAULT 0, reveal_on TEXT,
  source TEXT NOT NULL, transcript TEXT,
  created_by INTEGER NOT NULL REFERENCES user(id),
  created_at TEXT NOT NULL, updated_at TEXT, deleted_at TEXT,
  transfer_group TEXT,
  recurring_id INTEGER REFERENCES recurring(id), recurring_month TEXT,
  UNIQUE (recurring_id, recurring_month));
CREATE INDEX entry_month ON entry (wallet_id, date);
CREATE TABLE fx_rate (date TEXT NOT NULL, currency TEXT NOT NULL, rate TEXT NOT NULL,
  PRIMARY KEY (date, currency));
```

- [ ] **Step 3: Write `002_seed.sql`**: the household wallet `('Közös', NULL)`; expense categories in this order: Élelmiszer, Háztartás, Higiénia, Rezsi, Lakhatás, Közlekedés, Autó, Egészség, Gyerek, Ruha, Étterem és kávé, Szórakozás, Ajándék, Előfizetések, Telefon és internet, Biztosítás, Járulék és adó, Zsebpénz, Egyéb; income: Fizetés, Pedikűr, Egyéb bevétel. No limits set.

- [ ] **Step 4: Write `test_schema.py`**: `test_seed_has_one_household_wallet` (exactly one wallet with NULL owner), `test_amount_must_be_positive` (insert `amount_minor=0` raises `IntegrityError`), `test_recurring_month_unique` (two entries with the same `recurring_id, recurring_month` raise), `test_zsebpenz_category_exists`.

- [ ] **Step 5: Implement `clock.today() -> str`** (`datetime.now(ZoneInfo("Europe/Bratislava")).date().isoformat()`) **and `now_utc() -> str`**, the models, and `main.py` with lifespan (migrate, `Database`, templates) and `GET /health`. `test_today_is_local`: freeze `datetime` at `2026-11-30T23:30:00Z` (00:30 local on 12-01) and assert `today() == "2026-12-01"`.

- [ ] **Step 6: Run** `pytest -q` - all pass. `docker compose build` succeeds.

- [ ] **Step 7: Commit** `feat(haztartas): stack skeleton, schema and seed`

---

### Task 2: Authentication, roles and the CLI

**Files:**
- Create: `app/security.py` (copy + roles), `app/routers/auth.py`, `app/cli.py`, `app/strings/hu.py`, `templates/login.html` (unstyled until Task 8), `tests/test_security.py`, `tests/test_auth_routes.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1 models.
- Produces: `security.require_user(request) -> User`, `security.require_adult(user) -> User` (403 for a child), `security.require_user_json(request) -> User` (401 `{"detail":"login"}` instead of a redirect, for `/capture/sync`); `cli.create_user(username, name, role) -> None` which, for `role="child"`, also creates `Wallet(name=f"{name} zsebpénze", owner_user_id=user.id)` in the same transaction.

- [ ] **Step 1: Tests**: Pedikur's `test_security.py` and `test_auth_routes.py` copied and adapted (`is_admin` -> `role`); plus `test_child_gets_wallet_on_create`, `test_adult_gets_no_wallet`, `test_require_adult_403_for_child`, `test_require_user_json_401_not_303`, `test_session_cookie_max_age_90_days_and_rolling` (log in, then GET the test-only guarded route from Pedikur's conftest; its response carries `Set-Cookie` with `Max-Age=7776000`). conftest gets fixtures `adult`, `adult2`, `child` (logged-in `TestClient`s sharing one app and DB).

- [ ] **Step 2: Run** - fail.

- [ ] **Step 3: Implement.** `SessionMiddleware(max_age=7776000, same_site="lax", https_only=settings.https_only)`. CLI usage: `python -m app.cli create-user <username> <name> --role adult|child`, `reset-password <username>`; minimum password length 10 as in Pedikur.

- [ ] **Step 4: Run** - pass. **Step 5: Commit** `feat(haztartas): login, adult and child roles, CLI`

---

### Task 3: Money, local time and exchange rates

**Files:**
- Create: `app/money.py`, `app/fx.py`, `tests/test_money.py`, `tests/test_fx.py`, `tests/fixtures/ecb-90d.xml` (trimmed real file: 3 days, EUR/HUF/CZK)
- Modify: `app/clock.py`

**Interfaces:**
- Produces:
  - `clock.scheduled_day(month: str, day_of_month: int) -> str` - the day clamped to the month's length.
  - `parse_amount(text: str) -> int` - minor units, raises `ValueError` on anything else.
  - `fmt_money(minor: int, currency: str) -> str` - `"12,50 EUR"`, `"12 000 Ft"` (HUF drops `,00`), `"-3,40 EUR"`.
  - `fx.parse_ecb(xml: bytes) -> list[tuple[str, str, Decimal]]` (date, currency, rate per 1 EUR).
  - `fx.store(session, rows) -> int` (upsert, returns rows written).
  - `fx.rate_for(session, day: str, currency: str) -> Decimal | None` - `Decimal(1)` for EUR; else the latest rate with `date <= day`; `None` if none.
  - `fx.to_eur_minor(amount_minor: int, rate: Decimal) -> int` - `amount / rate`, `ROUND_HALF_UP` to an integer.
  - `fx.daily_task(db)` - async; fetches `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml` with httpx at start and every 24 h, stores, logs and survives failure. The 90-day file every time backfills any gap with one call.

- [ ] **Step 1: Tests**:

```python
@pytest.mark.parametrize("text,minor", [
    ("12,50", 1250), ("12.50", 1250), ("12,5", 1250), ("12", 1200),
    ("1 200", 120000), ("1200", 120000), ("1.200,50", 120050), (" 7 ", 700)])
def test_parse_amount_accepts(text, minor): assert parse_amount(text) == minor

@pytest.mark.parametrize("text", ["", "abc", "-3", "0", "1,2,3", "12,345"])
def test_parse_amount_rejects(text):
    with pytest.raises(ValueError): parse_amount(text)

def test_fmt_money_huf_has_no_decimals(): assert fmt_money(120000, "HUF") == "1 200 Ft"
def test_fmt_money_negative(): assert fmt_money(-150, "EUR") == "-1,50 EUR"
def test_rate_for_weekend_uses_friday(...)   # fixture has 2026-11-13 (Fri); ask for 11-15
def test_rate_for_unknown_currency_is_none(...)
def test_rate_for_eur_is_one(...)
def test_to_eur_minor_rounds_half_up(): assert to_eur_minor(36560, Decimal("365.6")) == 100
def test_store_is_idempotent(...)          # storing the fixture twice leaves 9 rows
def test_scheduled_day_clamps():
    assert scheduled_day("2026-02", 31) == "2026-02-28"
    assert scheduled_day("2028-02", 31) == "2028-02-29"
    assert scheduled_day("2026-04", 31) == "2026-04-30"
```

A dot followed by exactly three digits is a thousands separator ("1.200"); a comma or dot followed by one or two digits is the decimal mark. "12,345" is ambiguous and rejected.

- [ ] **Step 2: Run** - fail. **Step 3: Implement** with `xml.etree.ElementTree` and `decimal`. **Step 4: Run** - pass.
- [ ] **Step 5: Commit** `feat(haztartas): amount parsing, money display, ECB rates`

---

### Task 4: Visibility and edit rules

The most important task in the phase: every leak of a hidden entry would come from here.

**Files:**
- Create: `app/services/visibility.py`, `tests/test_visibility.py`

**Interfaces:**
- Consumes: models, `clock.today()`.
- Produces:
  - `View = Literal["full", "redacted", "none"]`
  - `is_secret(entry, today: str) -> bool` - `hidden` and (`reveal_on` is NULL or `reveal_on > today`).
  - `view_of(viewer: User, entry: Entry, wallet: Wallet, today: str) -> View`
  - `can_edit(viewer: User, entry: Entry, wallet: Wallet, today: str) -> bool`
  - `listable(viewer: User, today: str) -> ColumnElement[bool]` - SQL filter on `Entry` (joined to `Wallet`) for rows the viewer may see at all, `deleted_at IS NULL` included.
  - `text_searchable(viewer: User, today: str) -> ColumnElement[bool]` - rows whose merchant/note/transcript may be matched by this viewer's search: author, or not secret.

Rules (spec section 2), implemented exactly:

First matching row wins.

| | `view_of` | `can_edit` |
|---|---|---|
| entry belongs to a `transfer_group` | (rows below) | no, for anyone: delete removes both halves |
| viewer is the author | full | yes |
| adult, entry secret, not author | redacted | no |
| adult, entry not secret | full | yes |
| child, entry not by child and not in child's wallet | none | no |
| child, entry in child's wallet, by an adult (top-up) | full | no |

Redacted exposes exactly: `id, amount_minor, currency, eur_minor, category_id, date, created_by, hidden`. Task 9's templates receive a `RedactedEntry` dataclass with only those fields, never the ORM object, so a template cannot reach `merchant` by mistake.

- [ ] **Step 1: Tests**: one test per table row, plus `test_reveal_on_today_is_full` (`reveal_on == today` -> full), `test_reveal_on_tomorrow_is_redacted`, `test_child_hidden_entry_redacted_for_adult`, `test_listable_child_sees_only_own_and_wallet`, `test_listable_excludes_deleted`, and Review Focus 3:

```python
def test_search_never_matches_others_hidden_text(s, adult, adult2):
    add_entry(s, author=adult2, merchant="Parfümória", hidden=True)
    rows = s.scalars(select(Entry).join(Wallet)
        .where(listable(adult, TODAY), text_searchable(adult, TODAY),
               func.fold(Entry.merchant).contains("parfum"))).all()
    assert rows == []
```

- [ ] **Step 2: Run** - fail. **Step 3: Implement.** **Step 4: Run** - pass.
- [ ] **Step 5: Commit** `feat(haztartas): visibility and edit rules`

---

### Task 5: Entries service

**Files:**
- Create: `app/services/entries.py`, `tests/test_entries.py`

**Interfaces:**
- Consumes: Tasks 3 and 4.
- Produces:

```python
@dataclass
class EntryInput:
    wallet_id: int; kind: str; date: str; amount_minor: int; currency: str
    category_id: int | None; merchant: str | None; note: str | None
    payment: str; hidden: bool; reveal_on: str | None
    manual_rate: Decimal | None = None; client_uuid: str | None = None
    source: str = "manual"

class NeedsRate(Exception): ...        # no ECB rate and no manual_rate
class NotAllowed(Exception): ...       # role, wallet or edit rule refused

def create_entry(s, author: User, data: EntryInput, status: str = "confirmed") -> Entry
def update_entry(s, viewer: User, entry_id: int, data: EntryInput) -> Entry
def delete_entry(s, viewer: User, entry_id: int) -> None
def reveal_entry(s, viewer: User, entry_id: int) -> None
def find_duplicates(s, viewer: User, data: EntryInput) -> list[DuplicateHint]
def top_up(s, adult: User, child_wallet_id: int, amount_minor: int,
           currency: str, day: str) -> tuple[Entry, Entry]
```

`DuplicateHint(entry_id, eur_minor, merchant: str | None, author_name, created_at, hidden: bool)` - `merchant` is `None` when the hint is a secret entry of someone else.

Rules:
- **Allowed targets** (`create_entry`): household wallet - adult any kind, child expense only; child's own wallet - the child (expense or income) and adults (income only: opening balance, gift); another child's wallet - nobody. Else `NotAllowed`.
- **Idempotent:** an existing `client_uuid` returns the existing entry unchanged (no second row, no error).
- `eur_minor`/`fx_rate` from `fx.rate_for`, else `manual_rate`, else `NeedsRate`.
- `delete_entry` sets `deleted_at` on the entry and on every entry sharing its `transfer_group`.
- `reveal_entry`: author only; sets `hidden = 0`.
- `find_duplicates`: same wallet, `date` equal to the input's or the day before, `|eur_minor - candidate.eur_minor| <= 2%` of the larger, status confirmed, not deleted, only rows `listable` for the viewer. Phase 1 offers "save anyway" and "cancel"; merge arrives with photos in phase 2.
- `top_up`: one `transfer_group` uuid; household expense in category "Zsebpénz", child-wallet income in "Egyéb bevétel", same amount, currency and date.

- [ ] **Step 1: Tests**: `test_create_is_idempotent_on_client_uuid`, `test_child_cannot_add_household_income`, `test_adult_cannot_add_expense_to_child_wallet`, `test_child_can_add_income_to_own_wallet`, `test_huf_entry_gets_eur_at_save`, `test_unknown_currency_needs_rate`, `test_manual_rate_used`, `test_update_recomputes_eur_when_date_changes`, `test_update_others_secret_not_allowed`, `test_delete_top_up_removes_both`, `test_reveal_by_non_author_not_allowed`, `test_duplicate_found_within_2_percent_and_yesterday`, `test_duplicate_not_found_two_days_back`, `test_duplicate_hint_hides_secret_merchant`, `test_child_never_gets_hint_about_adult_entries`.
- [ ] **Step 2: Run** - fail. **Step 3: Implement.** **Step 4: Run** - pass.
- [ ] **Step 5: Commit** `feat(haztartas): entries service`

---

### Task 6: Month summary

**Files:**
- Create: `app/services/summary.py`, `tests/test_summary.py`

**Interfaces:**
- Produces:

```python
@dataclass
class CategoryLine: category_id: int; name: str; spent_eur_minor: int; limit_eur_minor: int | None
@dataclass
class ExpectedIncome: name: str; day: str; amount_minor: int; currency: str
@dataclass
class MonthSummary:
    month: str; categories: list[CategoryLine]
    income_eur_minor: int; expense_eur_minor: int; balance_eur_minor: int
    by_author: list[tuple[str, int]]; expected: list[ExpectedIncome]

def month_summary(s, month: str, today: str) -> MonthSummary     # callers: adults only
def wallet_balance(s, wallet_id: int) -> int                       # EUR minor, income - expense
```

- Household wallet only, confirmed, not deleted, `date LIKE 'YYYY-MM-%'`. Secret entries count in full.
- `categories`: every non-archived expense category with spending or a limit, ordered by `sort`.
- `expected`: income `recurring` items whose day in `month` (`clock.scheduled_day`) has no confirmed entry for that `recurring_month` yet.

- [ ] **Step 1: Tests**: `test_secret_entry_counts_in_category`, `test_child_wallet_not_in_household_totals`, `test_top_up_counts_once_as_zsebpenz`, `test_drafts_and_deleted_excluded`, `test_month_boundary_31st_in_month`, `test_expected_income_disappears_when_confirmed`, `test_wallet_balance_after_top_up_and_spend`.
- [ ] **Step 2-4:** fail, implement, pass. **Step 5: Commit** `feat(haztartas): month summary`

---

### Task 7: Recurring items and drafts

**Files:**
- Create: `app/services/recurring.py`, `tests/test_recurring.py`
- Modify: `app/main.py` lifespan (start `recurring.daily_task` and `fx.daily_task` next to `backup.nightly_task`)

**Interfaces:**
- Consumes: `clock.scheduled_day`, `entries.create_entry`.
- Produces: `create_due_drafts(s, today: str) -> int` (drafts for every active recurring item whose scheduled day this month is `<= today` and which has no entry for this `recurring_month`; author = `owner_user_id` or the first adult; household wallet); `confirm_draft(s, adult: User, entry_id: int, data: EntryInput | None) -> Entry` (any adult; applies `data` if given, sets `status='confirmed'`); `async daily_task(db)` (at start and hourly - cheap and idempotent, so a container restarted at 00:30 still catches the day).

- [ ] **Step 1: Tests**: `test_draft_created_once` (run twice, one draft), `test_not_before_its_day`, `test_child_cannot_confirm`, `test_confirm_with_corrected_amount`.
- [ ] **Step 2-4:** fail, implement, pass. **Step 5: Commit** `feat(haztartas): recurring drafts`

---

### Task 8: Design foundation (inline, `impeccable`, screenshot loop) - CHECKPOINT

**Files:**
- Create: `static/tokens.css`, `static/app.css`, `static/htmx.min.js` (2.x, copied from Pedikur), `templates/base.html`, restyle `templates/login.html`, `templates/home.html` (static mock data from a fixture, no service calls yet)

- [ ] **Step 1:** Run `impeccable` (shape) on the brief: Hungarian, phone-first, one-handed; the home screen leads with three large capture actions (Fotó, Hang, Kézi - Fotó and Hang shown disabled with "hamarosan" in phase 1), then balance and the category bars; a child sees their wallet instead of the household money. Own small token set, not `brand/`.
- [ ] **Step 2:** Screenshot loop at 390x844 and 360x780: login, adult home, child home. Both light and dark if the tokens define dark.
- [ ] **Step 3: STOP.** Show the screenshots to the owner; continue only after a yes on the direction.
- [ ] **Step 4: Commit** `feat(haztartas): design foundation`

---

### Task 9: Home, entry form and entry list

**Files:**
- Create: `routers/home.py`, `routers/entries.py`, `templates/home.html` (real data), `templates/entry_form.html`, `templates/entries.html`, `templates/partials/duplicate_hint.html`, `tests/test_entries_routes.py`, `tests/test_home_routes.py`

**Interfaces:**
- Consumes: Tasks 4-6. Routes: `GET /` (`?month=`), `GET /entries` (`?month&wallet&category&author&q`), `GET /entries/new`, `POST /entries`, `GET /entries/{id}`, `POST /entries/{id}`, `POST /entries/{id}/delete`, `POST /entries/{id}/reveal`.

- Form defaults: date `clock.today()`, currency EUR, payment card, wallet household. A child's wallet choice is "Közös" or their own. Hidden toggle reveals an optional `reveal_on` date. Under the category select, one line: `S["category_business_hint"]` = "Pedikűrös anyag? Azt a Pedikur appba rögzítsd."
- `POST /entries`: `ValueError` from `parse_amount` or `NeedsRate` re-renders the form with the message and the typed values, status 422. If `find_duplicates` returns hints and the form has no `confirm_duplicate=1`, re-render with the hint partial ("Mégis mentem" / "Mégse"). Secret hint text: `S["duplicate_secret"]` = "Egy rejtett tétel hasonló összeggel".
- List rows: full entries normally; redacted entries render via `RedactedEntry` as "Rejtett tétel" + amount, category, author, date; no link to a detail page. `q` searches `fold(merchant)`, `fold(note)` under `text_searchable`.
- Home for a child: their wallet balance and their last 20 entries; no household money anywhere in the HTML.

- [ ] **Step 1: Tests**: `test_child_home_has_no_household_balance` (response text contains neither the balance label nor the formatted balance), `test_redacted_row_has_no_merchant` (adult2's secret "Parfümória" absent from adult's `/entries` HTML), `test_redacted_entry_detail_404_for_others`, `test_bad_amount_422_keeps_values`, `test_duplicate_prompt_then_save_anyway`, `test_child_cannot_post_household_income_403`, `test_search_finds_own_hidden`.
- [ ] **Step 2-4:** fail, implement, pass; screenshot loop on every new screen.
- [ ] **Step 5: Commit** `feat(haztartas): home, entry form, entry list`

---

### Task 10: Drafts, pocket money and settings

**Files:**
- Create: `routers/drafts.py`, `routers/pocket.py`, `routers/settings.py`, templates for each, `tests/test_drafts_routes.py`, `tests/test_pocket_routes.py`, `tests/test_settings_routes.py`

**Interfaces:**
- `GET /drafts`, `POST /drafts/{id}/confirm` (adult; same fields as the entry form). Home shows a "N tervezet vár" link when drafts exist.
- `GET /pocket` - child: balance + own wallet entries; adult: each child wallet's balance and entries, item by item. `POST /pocket/topup` (adult): `top_up`. `POST /pocket/opening` (adult): income into the child wallet, category "Egyéb bevétel", note "Nyitó egyenleg".
- `GET /settings` (adult): categories (rename, monthly limit in EUR, archive, add, reorder by a number field) and recurring items (add, edit, archive). No user management (CLI).

- [ ] **Step 1: Tests**: `test_child_settings_403`, `test_child_drafts_403`, `test_topup_creates_pair_visible_to_child`, `test_set_limit_shows_on_home`, `test_archived_category_not_in_form_but_history_keeps_name`.
- [ ] **Step 2-4:** fail, implement, pass; screenshot loop.
- [ ] **Step 5: Commit** `feat(haztartas): drafts, pocket money, settings`

---

### Task 11: Installable PWA and the offline capture queue

**Files:**
- Create: `routers/capture.py`, `static/capture.js`, `static/sw.js`, `static/manifest.webmanifest`, icons, `templates/capture.html`, `tests/test_capture_routes.py`
- Modify: `main.py` (`GET /sw.js` and `GET /manifest.webmanifest` served from the root - Pedikur's `service_worker()` comment explains why), `templates/base.html` (pending counter element, `capture.js` on every page)

**Interfaces:**
- `GET /capture` - the manual form as a standalone page; works from cache offline. Categories and wallets for this user are rendered into it; the service worker caches it on every online visit, so the cached copy is the last one seen.
- `POST /capture/sync` - JSON `EntryInput` fields with `amount` as the typed text and a required `client_uuid`; `require_user_json`. Responses: `200 {"client_uuid", "entry_id", "status"}`; `422 {"client_uuid", "error"}` for a bad amount or missing rate (item stays queued and is marked for the user to fix: it goes back into the form when opened); `401` without a session.
- If `find_duplicates` finds a hint, the entry is created as a **draft** (the person could not see the prompt offline) and appears on `/drafts`.

`capture.js`:
- IndexedDB store `queue`, key `client_uuid` (`crypto.randomUUID()`), value `{kind: "manual", payload, created_at, error?}`; the `kind` field and an optional `blob` slot exist so phase 2 adds photo and audio without migrating the store.
- Submit: write to the queue first, then try to sync. A form submission never depends on the network.
- Sync on load, on `online`, and after each submit; one item at a time, in order; `fetch(..., {redirect: "manual"})`. Remove an item only on a 2xx JSON response whose `client_uuid` matches. On 401 or an opaque redirect: stop, keep everything, show `S["queue_login"]` "Jelentkezz be a feltöltéshez" linking to `/login`.
- Counter on every page: `S["queue_pending"]` "{n} tétel vár feltöltésre", hidden at 0.
- `navigator.storage.persist()` on first load. Logout clears the cache storage (not the queue).

`sw.js`: cache name `haztartas-v1`; precache `/capture`, `tokens.css`, `app.css`, `capture.js`, `htmx.min.js`; network-first for `/capture` and `/static/*`, falling back to cache; nothing else is cached (no household data at rest beyond the capture form).

- [ ] **Step 1: Tests**: `test_sync_without_session_is_401_json`, `test_sync_twice_one_entry`, `test_sync_bad_amount_422_echoes_uuid`, `test_sync_duplicate_becomes_draft`, `test_sw_served_from_root_with_js_type`, `test_manifest_served`.
- [ ] **Step 2-4:** fail, implement, pass.
- [ ] **Step 5: Phone test, by hand** (on a real Android phone, Chrome, app installed to the home screen), each result written into the commit message:
  1. Flight mode on, record two entries, close the app, reopen: counter shows 2.
  2. Flight mode off: counter goes to 0 within seconds, both entries listed once.
  3. Log out (online). Flight mode on, open the app: the cached `/capture` form opens; record one entry. Flight mode off: the counter stays 1 and the login prompt shows. Log in: it uploads.
  4. Record the same amount as an existing entry offline: after sync it waits under drafts.
- [ ] **Step 6: Commit** `feat(haztartas): installable PWA, offline capture queue`

---

### Task 12: Deploy, README, Pangolin

Outward-facing: confirm with the owner before creating the Pangolin resource.

**Files:**
- Create: `README.md` (sections: Run, Users, Reverse proxy, Password reset, Backup, Restore, Rollback a bad deploy - Pedikur's README as the template)

- [ ] **Step 1:** On LXC 100: `mkdir -p /srv/docker-data/haztartas && chown 1000:1000 /srv/docker-data/haztartas`. Komodo stack `haztartas` from this repo path, Stack Environment `HAZTARTAS_SECRET_KEY` (generated with `python -c "import secrets;print(secrets.token_urlsafe(48))"`). Deploy; `curl -s 192.168.0.110:3011/health` returns `ok`; container `healthy`.
- [ ] **Step 2:** Users: two adults and the child via `docker compose exec haztartas python -m app.cli create-user ...`. Passwords go to the family directly, never into the repo or a chat log.
- [ ] **Step 3:** Pangolin resource for the subdomain (the real name stays out of the public docs; README uses `haztartas.example`), rules in this order: Bypass Country SK, Bypass Country HU, everything else Pangolin SSO. Verify from outside over mobile data: `/login` loads without a Pangolin login from SK.
- [ ] **Step 4:** Backup check: after the first night, `ls /srv/docker-data/haztartas/backup/` shows a `daily-*.sqlite`, and `sqlite3 <it> 'PRAGMA integrity_check'` prints `ok`.
- [ ] **Step 5:** Install the PWA on each of the three phones; run Task 11's phone test once more against production.
- [ ] **Step 6:** Update the spec's section 0 table (phase 1: deployed, date) and commit `feat(haztartas): phase 1 deployed`.

## Definition of done for phase 1

- All tests pass in the container (`docker compose exec haztartas pytest -q`).
- Three users can log in on their own phones, from the installed app, over mobile data in SK.
- An entry recorded in flight mode arrives once after reconnecting.
- A hidden entry shows only its amount, category, date and author to the other adult and is absent for the child.
- The month view's numbers for a seeded test month were checked by hand against the entries list.
