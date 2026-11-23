# Haztartas Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Receipt photo (eKasa QR first, then Gemini) and voice capture (Gemini audio), queued offline like the manual form, ending on a confirm screen with per-line categories that remembers corrections; drafts confirmable by the right person; duplicate merge.

**Architecture:** One new upload endpoint saves the file and an empty draft, commits, then extracts inside the same request (eKasa, then Gemini) with async httpx outside any DB session, and fills the draft. Line items live in `entry_line`; budgets count lines by their own category except for a secret entry. The offline queue (`capture.js`) gains `photo` and `audio` items carrying a Blob. No new dependency: Gemini and eKasa are plain REST through the already pinned `httpx`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, SQLite (WAL), Jinja2 + htmx, httpx (async), pytest; vanilla JS (`BarcodeDetector`, canvas, `MediaRecorder`, IndexedDB).

**Spec:** `docs/superpowers/specs/2026-11-15-haztartas-design.md` (sections 2, 3.2-3.7, 5, 8, 9, 12). Code root: `compose/proxmox-lxc-100/haztartas/`. All paths below are relative to it unless they start with `docs/`.

## Owner hand-offs (blocking points)

| Needed by | What | How |
|---|---|---|
| Task 6 | Three real Slovak receipt QR texts: one with a discount line, one with a bottle deposit, one offline-issued if one turns up | The owner pastes the QR text (not a photo) into the chat; it is a receipt id, not a secret |
| Task 10 step "voice format gate", Task 11 | `HAZTARTAS_GEMINI_KEY` from a Google Cloud project **with an active billing account** (spec 5: EEA terms effective 2026-03-23) | The owner puts it in the Komodo Stack Environment of `haztartas` and, for the smoke runs from LXC 109, in `/root/.secrets/haztartas-secrets` (0600). Never in the chat |

Tasks 1-5 and 7-9 need neither. If Task 6 is reached without the QR texts, stop and ask; do not invent eKasa field names.

## Execution mode

As phase 1: **a fresh implementer subagent per task and a fresh review subagent per task** (given `git show` of the task, this task's section, and the spec), then one whole-branch review at the end on the most capable model. **Screens are never delegated**: Tasks 4 (UI part), 8 and 10 render templates and CSS in the main session with the screenshot loop (`scripts/shot.mjs`, 390 and 360 px, `impeccable`, `DESIGN.md`); their Python parts may go to a subagent first. Work on a branch `haztartas-phase2`; merge, push and deploy only when the owner says so.

Run tests from the app dir: `/root/homelab/.superpowers/venv/bin/python -m pytest -q`. Baseline before Task 1: 325 passed.

## Global Constraints

- Everything from the phase 1 plan's Global Constraints still holds (integer minor units, local dates via `app.clock.today()`, soft delete, the child's wallet in no household total, strings in `app/strings/hu.py`, English in the repo, no em dashes).
- **No new Python dependency.** Gemini and eKasa through `httpx.AsyncClient`; no Google SDK, no Pillow, no ffmpeg in the image.
- **No DB session is open across an outside call.** `Database.session()` begins with `BEGIN IMMEDIATE` (`app/db.py`), so a session held across a 45 s Gemini call blocks every other writer past its 5 s busy timeout. Pattern: session (save) -> commit -> `await` outside call -> new session (fill).
- **Outside calls are async** (`await client.post(...)`), never sync httpx inside an `async def` route: a sync call would freeze the app for all three users while it waits.
- Env: `HAZTARTAS_GEMINI_KEY` (optional; empty = extraction skipped, the draft stays empty with its file, a warning is logged at startup), `HAZTARTAS_GEMINI_MODEL` (default `gemini-3.8-flash`).
- Gemini endpoint: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`, header `x-goog-api-key`, body `contents[0].parts = [{inlineData: {mimeType, data: <base64>}}, {text: prompt}]`, `generationConfig = {responseMimeType: "application/json", responseJsonSchema: <schema>}`.
- eKasa endpoint: `POST https://ekasa.financnasprava.sk/mdu/api/v1/opd/receipt/find`, JSON `{"receiptId": "O-..."}`; per call 10 s timeout; on HTTP 429/5xx or a timeout retry after 1 s, then 3 s; **the whole eKasa step stops at a 15 s deadline**, then Gemini. Sequential, never parallel.
- Time budget: eKasa 15 s + Gemini 35 s timeout keeps the server under ~50 s; the client aborts a media upload after **75 s** (`MEDIA_TIMEOUT_MS = 75000`), the manual form keeps its 20 s.
- Upload cap: **20 MB** per media upload (Gemini's inline request limit); over it -> `413` JSON echoing `client_uuid`.
- Money values in Gemini's schema are **strings** (`"84.30"`, `"-1.20"`), parsed with `Decimal`, never JSON numbers (floats).
- Attachments: `media/<YYYY>/<client_uuid>.<ext>` under `settings.media_dir`, never under `/static`; served only through `GET /attachments/{id}`, which applies `visibility.view_of(...) == "full"` and 404s otherwise.
- Draft rule, one function: **confirmable by its author, or by an adult when not secret** (spec 3.7). The salary drafts follow the same rule (an adult is never their author's only confirmer).
- `sw.js` and `capture.js` cache name goes `haztartas-v3` -> `haztartas-v4` (both files, same commit).

## Review Focus

1. **A media upload retried while the first request is still extracting** (the phone timed out at the till and resent): one draft, the second answer carries the same `entry_id`, no second Gemini call. Task 7 `test_media_retry_returns_existing_draft_without_extracting`.
2. **Gemini returns messy values**: `"84,30"`, `"€"` or `"Ft"` as currency, a date `"2026-13-01"` or in the future, a category name not in the list, lines summing nowhere near the total, `null` everywhere. Each bad field becomes empty or defaulted; the draft is still created; never a 500. Task 5 `test_parse_tolerates_messy_values`.
3. **A hidden receipt leaks through a side door**: the attachment URL, a search by line name, the per-line budget split, the duplicate hint. Task 3 `test_secret_entry_counts_under_entry_category_only`, `test_search_by_line_name_skips_others_secret`; Task 7 `test_attachment_of_secret_entry_404_for_others`; Task 9 `test_merge_never_offers_secret_target`.
4. **Big or endless media**: a 25 MB photo (no canvas downscale on some browser) or a recording left running. Server `413` echoing the uuid (the client stores it as refused, not retried every 15 s); the recorder stops itself at 120 s. Task 7 `test_media_too_large_413_echoes_uuid`; Task 10 phone step "long recording".
5. **A receipt in a currency with no rate yet** (Gemini says `RSD`, or HUF before the first ECB fetch): the draft is created with `eur_minor` NULL and the confirm screen asks for a rate, as the manual form does; lines get their EUR split only at confirm. Task 8 `test_confirm_draft_without_rate_asks_and_then_splits_lines`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `app/migrations/003_receipts.sql` | entry rebuild (money nullable on drafts), `entry_line`, `attachment`, `line_category_rule` | 1 |
| `app/models.py` | `EntryLine`, `Attachment`, `LineCategoryRule`; `Entry` money columns optional | 1 |
| `app/services/lines.py` | line arithmetic and rules: normalise, rules lookup/remember, main category, adjustment line, EUR split, save lines | 2 |
| `app/services/summary.py`, `app/services/home.py`, `app/routers/entries.py` | per-line budgets, secret under one category, search by line name | 3 |
| `app/services/visibility.py`, `app/services/entries.py`, `app/routers/drafts.py`, `app/routers/pocket.py`, `app/services/home.py`, templates | `can_confirm`, generalised `confirm_draft`, who sees which draft | 4 |
| `app/extract/__init__.py` | `Extracted`, `ExtractedLine` dataclasses, shared value parsers | 5 |
| `app/extract/gemini.py` | schema, prompts, REST call, response parsing | 5 |
| `app/config.py`, `docker-compose.yml`, `.env.example` | Gemini env | 5 |
| `app/extract/ekasa.py`, `tests/fixtures/ekasa/*.json`, `scripts/ekasa_fetch.py` | QR text -> receipt id, lookup with retries, response parsing | 6 |
| `app/services/capture.py`, `app/routers/media.py` | upload: save, draft, extract, fill; attachment route | 7 |
| `app/templates/draft_confirm.html`, `app/templates/partials/lines.html`, `app/routers/drafts.py`, CSS | the receipt confirm screen | 8 |
| `app/services/entries.py` (`merge_draft`), `app/templates/partials/duplicate_hint.html` | duplicate merge | 9 |
| `app/static/capture.js`, `app/static/sw.js`, `app/templates/capture.html`, `app/templates/home.html`, `scripts/offline_check.mjs` | photo and voice capture, queue blobs | 10 |
| `scripts/gemini_smoke.py`, `README.md`, `docs/proxmox/56_Family_Budget_PWA.md`, spec section 0 | real-key checks, deploy, docs | 11 |

---

### Task 1: Schema for receipts

**Files:**
- Create: `app/migrations/003_receipts.sql`
- Modify: `app/models.py`
- Test: `tests/test_schema.py`, `tests/test_migrate.py`

**Interfaces:**
- Produces: tables and ORM classes below. `Entry.amount_minor`, `Entry.eur_minor`, `Entry.fx_rate` become `Mapped[int | None]` / `Mapped[str | None]`. `EntryLine(id, entry_id, pos, name, quantity: str | None, unit_price_minor: int | None, total_minor: int, eur_minor: int | None, category_id: int | None)`. `Attachment(id, entry_id, kind: 'photo'|'audio', path: str, mime: str, raw_json: str | None, created_at: str)`. `LineCategoryRule(merchant_key: str, line_key: str, category_id: int, updated_at: str)`, primary key `(merchant_key, line_key)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_schema.py
def test_draft_may_have_no_amount(users): ...
    # insert an Entry status='draft', amount_minor=None, eur_minor=None, fx_rate=None -> commits
def test_confirmed_needs_amount_and_rate(users): ...
    # same with status='confirmed' -> sqlalchemy.exc.IntegrityError
def test_amount_still_positive(users): ...
    # status='draft', amount_minor=0 -> IntegrityError
def test_line_total_may_be_negative(users): ...
    # EntryLine(total_minor=-120) on a draft -> commits
def test_lines_and_attachments_cascade_on_entry_delete(users): ...
    # raw DELETE FROM entry removes its entry_line and attachment rows (ON DELETE CASCADE)

# tests/test_migrate.py
def test_003_keeps_phase1_rows(tmp_path): ...
    # run 001+002, insert one confirmed entry with client_uuid, recurring_id and
    # transfer_group set, run 003: the row is identical column by column,
    # index entry_month exists, PRAGMA foreign_key_check returns nothing
```

- [ ] **Step 2: Run them, expect failures** (`pytest tests/test_schema.py tests/test_migrate.py -q`: the new tests fail on missing tables / NOT NULL)

- [ ] **Step 3: Write `003_receipts.sql`**

Rebuild `entry` (SQLite cannot alter a CHECK): `CREATE TABLE entry_new` with the 001 columns in the same order, except `amount_minor INTEGER CHECK (amount_minor IS NULL OR amount_minor > 0)`, `eur_minor INTEGER`, `fx_rate TEXT`, plus a table CHECK `(status = 'draft' OR (amount_minor IS NOT NULL AND eur_minor IS NOT NULL AND fx_rate IS NOT NULL))`; `INSERT INTO entry_new SELECT * FROM entry; DROP TABLE entry; ALTER TABLE entry_new RENAME TO entry; CREATE INDEX entry_month ON entry (wallet_id, date);`. This runs with `foreign_keys = ON` inside the migration transaction; it is safe only because no table references `entry` yet, so the three new tables come **after** the rename. Then:

```sql
CREATE TABLE entry_line (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
  pos INTEGER NOT NULL, name TEXT NOT NULL, quantity TEXT,
  unit_price_minor INTEGER, total_minor INTEGER NOT NULL, eur_minor INTEGER,
  category_id INTEGER REFERENCES category(id));
CREATE INDEX entry_line_entry ON entry_line (entry_id);
CREATE TABLE attachment (
  id INTEGER PRIMARY KEY,
  entry_id INTEGER NOT NULL REFERENCES entry(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('photo','audio')),
  path TEXT NOT NULL, mime TEXT NOT NULL, raw_json TEXT, created_at TEXT NOT NULL);
CREATE INDEX attachment_entry ON attachment (entry_id);
CREATE TABLE line_category_rule (
  merchant_key TEXT NOT NULL, line_key TEXT NOT NULL,
  category_id INTEGER NOT NULL REFERENCES category(id), updated_at TEXT NOT NULL,
  PRIMARY KEY (merchant_key, line_key));
```

Also seed the expense category `Eltérés`? **No**: the adjustment line takes the entry's main category (spec 3.7). Nothing seeded.

- [ ] **Step 4: Mirror it in `app/models.py`** (three classes, the three optional `Entry` columns).

- [ ] **Step 5: Run the whole suite**: `pytest -q`, expect 325 + 6 passed. A type-only ripple (a template formatting `None`) is fixed where it fails; drafts only ever reach `fmt_money` through `drafts.py`, which Task 4 rewrites.

- [ ] **Step 6: Commit** `feat(haztartas): schema for receipt lines and attachments`

---

### Task 2: Line arithmetic and category rules

**Files:**
- Create: `app/services/lines.py`
- Test: `tests/test_lines.py`

**Interfaces:**
- Consumes: Task 1 models; `app.db.fold`; `app.clock.now_utc`.
- Produces:
  - `normalise(text: str | None) -> str` - `fold`, then collapse whitespace, strip digits-only tokens and trailing unit noise like `1ks`, `kg`; used for both rule keys.
  - `suggest(s, merchant: str | None, lines: list[ExtractedLine]) -> list[ExtractedLine]` - a rule for `(normalise(merchant), normalise(line.name))` overrides `line.category_id`.
  - `remember(s, merchant: str | None, name: str, category_id: int) -> None` - upsert one rule.
  - `main_category(lines: list[tuple[int | None, int]]) -> int | None` - category with the largest summed `total_minor`; ties go to the lowest category id; lines with `None` category ignored.
  - `adjustment(total_minor: int, line_totals: list[int]) -> int` - `total_minor - sum(line_totals)` (0 when they agree).
  - `split_eur(entry_eur_minor: int, line_totals: list[int]) -> list[int]` - largest remainder: proportional shares of `entry_eur_minor` by `line_totals` (negative lines allowed) that sum to it exactly.
  - `save_lines(s, entry: Entry, lines: list[tuple[str, str | None, int | None, int, int | None]]) -> None` - replaces the entry's lines (`name, quantity, unit_price_minor, total_minor, category_id`), appends the adjustment line `S["line_adjustment"]` ("Eltérés") in the main category when the difference is non-zero, sets `entry.category_id = main_category(...)`, and when `entry.eur_minor` is set fills every line's `eur_minor` with `split_eur`.

`ExtractedLine` comes from Task 5's `app/extract/__init__.py`; to keep this task self-contained, create that module here with only the two dataclasses, and Task 5 adds its parsers:

```python
@dataclass
class ExtractedLine:
    name: str
    total_minor: int
    quantity: str | None = None
    unit_price_minor: int | None = None
    category_id: int | None = None

@dataclass
class Extracted:
    merchant: str | None = None
    date: str | None = None          # YYYY-MM-DD, already validated
    currency: str | None = None      # 3 uppercase letters, already validated
    total_minor: int | None = None   # > 0 or None
    payment: str | None = None       # 'cash' | 'card' | None
    category_id: int | None = None   # for a voice entry with no lines
    lines: list[ExtractedLine] = field(default_factory=list)
    transcript: str | None = None
```

- [ ] **Step 1: Failing tests**

```python
def test_split_eur_sums_exactly():
    assert sum(split_eur(1001, [333, 333, 334])) == 1001
    assert split_eur(1000, [500, 500]) == [500, 500]
def test_split_eur_with_negative_discount_line():
    parts = split_eur(840, [900, -60]); assert sum(parts) == 840 and parts[1] < 0
def test_adjustment_is_total_minus_lines():
    assert adjustment(8430, [7140, 990, 300]) == 0
    assert adjustment(8430, [7140, 990]) == 300
def test_main_category_largest_subtotal_then_lowest_id():
    assert main_category([(2, 500), (3, 400), (3, 200)]) == 3
    assert main_category([(5, 100), (4, 100)]) == 4
    assert main_category([(None, 900)]) is None
def test_normalise_folds_accents_and_noise():
    assert normalise("  MLIEKO  Rajo 1,5% 1L ") == normalise("mlieko rajo 1,5% 1l")
def test_rule_overrides_suggestion(users): ...   # remember(Lidl, "Jar 450ml", Háztartás) then suggest -> Háztartás
def test_rule_is_per_merchant(users): ...        # same line name at Tesco keeps Gemini's guess
def test_save_lines_adds_adjustment_in_main_category(users): ...
    # entry total 8430, lines 7140 (Élelmiszer) + 990 (Háztartás): a third line "Eltérés" 300, category Élelmiszer
def test_save_lines_replaces_previous_lines(users): ...
```

- [ ] **Step 2: Run, expect ImportError.**
- [ ] **Step 3: Implement `app/extract/__init__.py` (dataclasses only) and `app/services/lines.py`.** `split_eur`: floor each share `entry_eur * t // sum(t)` (Python floor division on signed ints), then hand the remaining units one by one to the largest fractional remainders; guard `sum(line_totals) == 0` by putting everything on the first line.
- [ ] **Step 4: Run, expect pass; full suite green.**
- [ ] **Step 5: Commit** `feat(haztartas): line arithmetic and remembered line categories`

---

### Task 3: Budgets per line, search by line name

**Files:**
- Modify: `app/services/summary.py`, `app/services/home.py` (child tiles), `app/routers/entries.py` (search)
- Test: `tests/test_summary.py`, `tests/test_home_routes.py`, `tests/test_entries_routes.py`

**Interfaces:**
- Consumes: Task 1 `EntryLine`; `visibility._secret` semantics (`hidden` and `reveal_on` null or in the future).
- Produces: `summary.spent_by_category(s, conds: tuple, today: str) -> dict[int, int]` - EUR minor per category for the expense entries matching `conds`: an entry with lines and **not secret** counts each line's `eur_minor` under the line's category; an entry without lines, or a secret one, counts `entry.eur_minor` under `entry.category_id`. Used by `month_summary` and the child branch of `home.build`.

- [ ] **Step 1: Failing tests**

```python
def test_lines_count_under_their_own_categories(users): ...
    # confirmed Tesco 30,00: lines 20,00 Élelmiszer + 10,00 Háztartás -> month_summary lines: 2000 / 1000
def test_secret_entry_counts_under_entry_category_only(users): ...
    # same receipt hidden (reveal_on None): 3000 under its main category, Háztartás 0
def test_revealed_entry_counts_per_line(users): ...
    # hidden with reveal_on <= today -> per line again
def test_total_unchanged_by_lines(users): ...
    # expense_eur_minor equals sum of entry eur_minor with or without lines
def test_search_by_line_name_finds_own_receipt(adult, users): ...
    # GET /entries?q=mosogep finds the entry whose line is "Mosogep tabletta"
def test_search_by_line_name_skips_others_secret(adult, adult2, users): ...
    # adult2's hidden receipt with line "Parfum" is not found by adult's q=parfum
```

- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement `spent_by_category`** as two grouped queries summed in Python (entries without lines or secret; lines of non-secret entries) and switch `month_summary` and the child tiles to it. Search: extend the `/entries` `q` condition with `Entry.id.in_(select(EntryLine.entry_id).where(func.fold(EntryLine.name).contains(needle, autoescape=True)))`, still inside `visibility.text_searchable(...)`.
- [ ] **Step 4: Run; full suite green.**
- [ ] **Step 5: Commit** `feat(haztartas): budgets count receipt lines by category`

---

### Task 4: Who confirms which draft

**Files:**
- Modify: `app/services/visibility.py`, `app/services/entries.py`, `app/services/recurring.py`, `app/routers/drafts.py`, `app/routers/pocket.py`, `app/services/home.py`, `app/templates/drafts.html`, `app/templates/pocket.html`, `app/templates/home.html`, `app/strings/hu.py`
- Test: `tests/test_visibility.py`, `tests/test_recurring.py`, `tests/test_drafts_routes.py`, `tests/test_pocket_routes.py`, `tests/test_home_routes.py`

**Interfaces:**
- Produces:
  - `visibility.can_confirm(viewer: User, entry: Entry, wallet: Wallet, today: str) -> bool` - `entry.status == "draft"` and not deleted and (`entry.created_by == viewer.id` or (`viewer.role == "adult"` and not `is_secret(entry, today)`)).
  - `visibility.confirmable(viewer: User, today: str) -> ColumnElement[bool]` - its SQL twin (drafts only), correct with or without a join, like `listable`.
  - `entries.confirm_draft(s, viewer: User, entry_id: int, data: EntryInput | None) -> Entry` - moved from `recurring.confirm_draft`, guarded by `can_confirm` (raises `NotAllowed`); `recurring.confirm_draft` is deleted and its tests move to `tests/test_entries.py`.
- Behaviour (spec 3.7):
  - `/drafts` (adults only, as today) lists every draft `confirmable` by the viewer **in any wallet**, the child's included, sorted by date; rows show `-` for an amount not yet known; the wallet name is in the meta line when it is not the household.
  - `/drafts/{id}` and `/drafts/{id}/confirm` take `require_user` and `can_confirm`; anything else 404. A child therefore reaches only their own drafts, and only by URL (Task 10 sends them there after an online upload).
  - Home: an adult's `drafts_count` counts `confirmable` drafts in all wallets.
  - Pocket money screen, child view: `S["drafts_waiting_parent"]` ("{n} tétel vár szülői jóváhagyásra") with the count of the child's own non-secret drafts, as text, no link; and a "Rejtett piszkozataim" list (`S["my_hidden_drafts"]`) of the child's own secret drafts linking to `/drafts/{id}`.

- [ ] **Step 1: Failing tests**

```python
@pytest.mark.parametrize("who,hidden,expect", [
    ("author_adult", False, True), ("author_adult", True, True),
    ("other_adult", False, True), ("other_adult", True, False),
    ("author_child", False, True), ("author_child", True, True),
    ("adult_on_child_draft", False, True), ("adult_on_child_draft", True, False),
    ("child_on_adult_draft", False, False),
])
def test_can_confirm_matrix(...): ...
def test_confirmable_sql_matches_python_without_join(users): ...
def test_salary_draft_still_confirmable_by_either_adult(users): ...
def test_drafts_list_shows_child_wallet_draft(adult, users): ...
def test_child_can_open_own_draft_but_not_list(child, users): ...   # /drafts/{id} 200, /drafts 403
def test_child_cannot_open_adult_draft(child, users): ...           # 404
def test_pocket_shows_waiting_count_and_hidden_list(child, users): ...
def test_confirm_never_moves_wallet(adult, users): ...              # existing behaviour, kept
```

- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement the service and routes** (subagent may do this part).
- [ ] **Step 4: Screens inline**: the drafts list rows with a wallet and a missing amount, the child's pocket page with the count and the hidden list; screenshot at 390 and 360 px, fix CSS, look again.
- [ ] **Step 5: Full suite green. Commit** `feat(haztartas): drafts confirmable by author or any adult`

---

### Task 5: Gemini extraction client

**Files:**
- Modify: `app/extract/__init__.py` (value parsers), `app/config.py`, `docker-compose.yml`, `.env.example`
- Create: `app/extract/gemini.py`, `tests/fixtures/gemini/*.json`, `scripts/gemini_smoke.py`
- Test: `tests/test_gemini.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: Task 2 `Extracted`, `ExtractedLine`.
- Produces:
  - `Settings.gemini_key: str | None`, `Settings.gemini_model: str` (`HAZTARTAS_GEMINI_KEY`, `HAZTARTAS_GEMINI_MODEL`, default `"gemini-3.8-flash"`); compose passes both with `${...:-}` defaults (empty key allowed).
  - In `app/extract/__init__.py`: `parse_money(text: str | None, currency: str | None) -> int | None` (accepts `"84.30"`, `"84,30"`, `"1 299"`, `"-1.20"`; minor units; `None` on anything else), `parse_currency(text) -> str | None` (`"€"`/`"eur"` -> `EUR`, `"Ft"`/`"HUF"` -> `HUF`, `"Kč"` -> `CZK`, any `[A-Z]{3}` kept, else `None`), `parse_day(text, today: str) -> str | None` (valid `YYYY-MM-DD`, not after `today`, not more than 1 year before).
  - `gemini.SCHEMA: dict` - JSON Schema: `merchant` string|null, `date` string|null, `currency` string|null, `total` string|null, `payment` enum `cash`,`card`,null, `category` string|null, `transcript` string|null, `lines` array of `{name: string, quantity: string|null, unit_price: string|null, total: string, category: string|null}`. Money as strings (Global Constraints).
  - `async def photo(client: httpx.AsyncClient, key: str, model: str, image: bytes, mime: str, categories: dict[str, int], today: str) -> tuple[Extracted, dict]` - returns the parsed result and the raw response JSON (stored as `attachment.raw_json`).
  - `async def audio(client, key, model, data: bytes, mime: str, categories, today) -> tuple[Extracted, dict]` - same schema; `transcript` required in the prompt.
  - `async def categorise(client, key, model, merchant: str | None, names: list[str], categories) -> list[int | None]` - text only, for eKasa lines; returns one category id (or None) per name, same order.
  - `parse_response(raw: dict, categories: dict[str, int], today: str) -> Extracted` - pure; `categories` maps the household's non-archived **expense** category names to ids; a name not in it -> `None`.
  - `class ExtractionFailed(Exception)` - raised for HTTP errors, timeouts, blocked or empty candidates, non-JSON text.
- Prompts: Hungarian household context, "the category must be one of: <names>", "money as a string with a dot decimal separator", "lines exactly as printed, discounts as negative lines". Wording is the builder's (spec 12), kept as module constants.

- [ ] **Step 1: Failing tests** (all with `httpx.MockTransport`, no network)

```python
def test_request_shape(): ...
    # URL .../v1beta/models/gemini-3.8-flash:generateContent, header x-goog-api-key,
    # parts[0].inlineData.mimeType == "image/jpeg", generationConfig.responseMimeType == "application/json",
    # generationConfig.responseJsonSchema == gemini.SCHEMA
def test_parse_receipt_fixture(): ...
    # fixture tesco_hu.json (a hand-written candidates[0].content.parts[0].text JSON):
    # merchant "Tesco", currency HUF, total 1_299_00, 3 lines, line categories mapped to ids
def test_parse_tolerates_messy_values(): ...
    # total "84,30" -> 8430; currency "€" -> EUR; date "2026-13-01" -> None; date tomorrow -> None;
    # category "Ismeretlen" -> None; total "-5" -> None; all-null JSON -> Extracted() with no lines
def test_http_error_raises_extraction_failed(): ...   # 400, 429, 500, timeout, candidates [] , text "not json"
def test_categorise_keeps_order_and_length(): ...
def test_settings_gemini_defaults(monkeypatch): ...   # key None when unset or blank, model default
```

- [ ] **Step 2: Run, expect failures.**
- [ ] **Step 3: Implement.** Timeout `httpx.Timeout(35.0)` per call. Log one info line per call: model, kind, seconds, `usageMetadata.totalTokenCount` (cost check), never the content.
- [ ] **Step 4: `scripts/gemini_smoke.py`** - reads `HAZTARTAS_GEMINI_KEY` from the environment, takes `--photo FILE` or `--audio FILE --mime TYPE`, calls `photo`/`audio` with a fixed category list, prints the `Extracted` and the latency. Not run in this task (no key); Tasks 10 and 11 run it.
- [ ] **Step 5: Full suite green. Commit** `feat(haztartas): Gemini extraction client`

---

### Task 6: eKasa lookup (blocked until the owner's QR texts arrive)

**Files:**
- Create: `scripts/ekasa_fetch.py`, `tests/fixtures/ekasa/*.json`, `app/extract/ekasa.py`
- Test: `tests/test_ekasa.py`

**Interfaces:**
- Consumes: Task 2 dataclasses, Task 5 parsers.
- Produces:
  - `receipt_id(qr_text: str | None) -> str | None` - the online receipt id form `O-` + 32 hex (case-insensitive, returned upper-case); anything else `None`. **Offline-issued receipts (an OKP-based QR) go to Gemini in this phase**; if the owner's offline sample shows the API accepts its fields, that is a follow-up, not this task.
  - `async def find(client: httpx.AsyncClient, rid: str, sleep=asyncio.sleep, deadline: float = 15.0) -> tuple[Extracted, dict] | None` - retry policy and deadline from Global Constraints; `None` when `receipt` is null, after the deadline, or on a non-JSON answer.
  - `parse(raw: dict) -> Extracted` - merchant (the shop or company name), date (issue date, local), currency `EUR`, total, lines with quantity, unit price and total (discount and deposit lines negative as the receipt states them). Field names come **from the fixtures**, not from this plan.

- [ ] **Step 1: Fetch the fixtures.** `scripts/ekasa_fetch.py ID...` POSTs each id (sequentially, 2 s apart) and writes `tests/fixtures/ekasa/<label>.json` pretty-printed. Run it with the owner's three ids. Open each file and note the item, total, date and merchant fields in the module docstring. Check the files hold no card number or personal data beyond the shop's; a receipt id itself is not personal data.
- [ ] **Step 2: Failing tests**

```python
def test_receipt_id_accepts_online_form(): ...   # "o-<32 hex>" -> "O-<32 HEX>"; "https://...?id=O-..." -> None unless the fixtures show URLs
def test_receipt_id_rejects_other_text(): ...     # "", None, OKP form, random URL
def test_parse_discount_fixture(): ...            # exact merchant, date, total, line count, one negative line; lines + adjustment == total
def test_parse_deposit_fixture(): ...             # the deposit line present with its sign as printed
def test_find_retries_then_gives_up_at_deadline(): ...  # MockTransport 429, 429, 429; fake sleep records [1, 3]; returns None
def test_find_null_receipt_returns_none(): ...    # {"returnValue":0,"receipt":null}
```

- [ ] **Step 3: Run, expect failures. Step 4: Implement. Step 5: Run; full suite green.**
- [ ] **Step 6: Commit** `feat(haztartas): eKasa receipt lookup with real fixtures`

---

### Task 7: Media upload, extraction pipeline, attachment route

**Files:**
- Create: `app/services/capture.py`, `app/routers/media.py`
- Modify: `app/main.py` (router, shared `httpx.AsyncClient` on `app.state.http` created in lifespan and closed on shutdown), `app/strings/hu.py`
- Test: `tests/test_media_routes.py`, `tests/test_capture_service.py`

**Interfaces:**
- Consumes: Tasks 1-6.
- Produces:
  - `capture.create_media_draft(s, author: User, client_uuid: str, kind: Literal["photo","audio"], wallet_id: int, hidden: bool, day: str, data: bytes, mime: str, media_dir: Path) -> Entry` - `_check_target` on the wallet (kind `expense`), writes the file, inserts the draft (`status="draft"`, `kind="expense"`, `currency="EUR"`, `payment="card"`, amounts NULL, `source` `photo`/`voice`) and its `Attachment`. Existing `client_uuid` of the same author returns that entry untouched; of another author raises `NotAllowed`.
  - `async def extract(http, settings, kind, data, mime, qr: str | None, categories, today) -> tuple[Extracted, dict | None, str]` - returns the result, the raw JSON and the `source` that produced it: `ekasa` when `receipt_id(qr)` found a receipt (then `gemini.categorise` for its lines, failures leave categories to the rules), else `photo`/`voice` from Gemini. No key -> `(Extracted(), None, kind source)`. `ExtractionFailed` is caught here and logged; the result is then empty.
  - `capture.fill_draft(s, entry_id: int, result: Extracted, raw: dict | None, source: str) -> Entry` - only while still a draft: applies `lines.suggest`, sets merchant, date, currency, amount (from `total_minor`, else the line sum when positive), payment, category (`main_category` of the lines or `result.category_id`), transcript, `source`; computes `eur_minor`/`fx_rate` when `fx.rate_for` has a rate, else leaves them NULL; `lines.save_lines`; stores `raw` on the attachment.
  - `POST /capture/media` (multipart: `file`, `client_uuid`, `kind`, `wallet_id`, `hidden`, `date`, `qr`, `user_id`), `require_user_json`. Answers like `/capture/sync`: JSON echoing `client_uuid`; `200 {entry_id, status: "draft", url: "/drafts/<id>"}`; `401` JSON without a session; `409` for another user's uuid or `user_id`; `403` for a wallet the user may not write; `413` over 20 MB (check `Content-Length` first, then the read size); `422` for a bad uuid, kind or mime (`image/jpeg`, `image/webp`, `audio/webm`, `audio/ogg`, `audio/wav`, `audio/mp4`).
  - Order inside the route (Global Constraints): session 1 `create_media_draft` + commit -> if it already existed, answer now without extracting -> `await capture.extract(...)` with no session open -> session 2 `fill_draft` -> answer.
  - `GET /attachments/{id}` (`require_user`): `FileResponse` with the stored mime, `Cache-Control: private, max-age=0`; 404 unless `visibility.view_of(viewer, entry, wallet, today) == "full"`.

- [ ] **Step 1: Failing tests** (Gemini and eKasa replaced by monkeypatching `capture.extract`, or by `httpx.MockTransport` on `app.state.http`)

```python
def test_media_upload_creates_filled_draft(adult, users, tmp_path): ...
    # extract returns Tesco 12,50 with 2 lines -> 200 JSON {client_uuid, entry_id, status "draft", url}
    # file exists under media/<YYYY>/<uuid>.jpg, attachment row, 2 lines, entry.source "photo"
def test_media_retry_returns_existing_draft_without_extracting(adult, users): ...
    # second POST same uuid -> same entry_id; extract called once
def test_extraction_failure_leaves_empty_draft_with_file(adult, users): ...
    # extract raises -> 200, draft with amount NULL, file and attachment kept
def test_no_gemini_key_gives_empty_draft(adult, users): ...
def test_ekasa_receipt_source_is_ekasa(adult, users): ...
def test_media_too_large_413_echoes_uuid(adult, users): ...
def test_media_without_session_401_json(client, users): ...
def test_media_other_users_uuid_409(adult, adult2, users): ...
def test_child_photo_into_household_wallet_allowed(child, users): ...
def test_child_photo_into_other_wallet_403(child, users): ...
def test_attachment_of_secret_entry_404_for_others(adult, adult2, users): ...
def test_attachment_visible_to_author_and_other_adult_when_not_hidden(adult, adult2, users): ...
def test_attachment_of_adult_entry_404_for_child(child, adult, users): ...
def test_no_session_open_during_extract(adult, users): ...
    # the patched extract performs a write through a fresh app.state.db.session(); it must not hit "database is locked"
```

- [ ] **Step 2: Run, expect failures. Step 3: Implement. Step 4: Run; full suite green.**
- [ ] **Step 5: Commit** `feat(haztartas): photo and audio upload into drafts`

---

### Task 8: The receipt confirm screen (inline, screenshot loop)

**Files:**
- Modify: `app/routers/drafts.py`, `app/templates/draft_confirm.html`, `app/static/app.css`, `app/strings/hu.py`
- Create: `app/templates/partials/lines.html`
- Test: `tests/test_drafts_routes.py`

**Interfaces:**
- Consumes: Task 2 `lines`, Task 4 `entries.confirm_draft`, Task 7 attachment route.
- Behaviour (spec 3.2 sketch):
  - Header: merchant, date, total. The photo as a thumbnail linking to `/attachments/{id}`; for a voice draft the transcript in a quiet paragraph.
  - Lines grouped by category: one row per category with count and subtotal (`<details>` per group, closed by default, no JS); inside, each line with name, amount and a category `<select name="line_cat_<line_id>">`.
  - The entry's category field is not shown when the draft has lines; the server sets it from `main_category` before `_build` (which requires one).
  - Line sum != total: a visible line `S["lines_mismatch"]` naming the difference; saving keeps the total and writes the adjustment line (Task 2).
  - On confirm, a line whose category differs from the one shown (the suggestion) calls `lines.remember(merchant, name, new_category)`.
  - EUR split of lines runs after `confirm_draft` set `eur_minor` (it may come from a manual rate).
- No line editing beyond category (spec: "a line can be moved to another category"). A wrong amount on a line shows up as the mismatch line.
- The confirmed entry's detail page (`/entries/{id}`, `entry_detail.html`) shows the same grouped lines read-only and the photo link, for a viewer with the full view only: this is how a search for "mosogep" ends at the warranty photo (spec 3.2). A redacted viewer never reaches the page (404 today, unchanged).

- [ ] **Step 1: Failing tests**

```python
def test_confirm_screen_groups_lines_by_category(adult, users): ...
def test_moving_a_line_remembers_rule(adult, users): ...
def test_confirm_sets_main_category_and_line_eur(adult, users): ...
def test_mismatch_is_shown_and_adjustment_saved(adult, users): ...
def test_confirm_draft_without_rate_asks_and_then_splits_lines(adult, users): ...
    # RSD draft: first POST 422 with the rate field; second with manual_rate -> confirmed, lines eur sum == entry eur
def test_voice_draft_shows_transcript(adult, users): ...
def test_other_adult_never_sees_secret_draft_lines(adult, adult2, users): ...   # 404 on /drafts/{id}
def test_entry_detail_shows_lines_and_photo_link(adult, users): ...
```

- [ ] **Step 2: Run, expect failures. Step 3: Implement routes and templates.**
- [ ] **Step 4: Screenshot loop** with a 40-line seeded receipt (three categories, one discount line, a 0,03 mismatch) and a voice draft, 390 and 360 px; the 40 lines must read as three closed rows at first sight.
- [ ] **Step 5: Full suite green. Commit** `feat(haztartas): receipt confirm screen with per-line categories`

---

### Task 9: Duplicate merge

**Files:**
- Modify: `app/services/entries.py`, `app/routers/drafts.py`, `app/templates/partials/duplicate_hint.html`, `app/strings/hu.py`
- Test: `tests/test_entries.py`, `tests/test_drafts_routes.py`

**Interfaces:**
- Produces: `entries.merge_draft(s, viewer: User, draft_id: int, target_id: int, data: EntryInput) -> Entry` - requires `can_confirm` on the draft and `can_edit` on the target, the target confirmed, not secret, same wallet. The target takes the draft's lines, attachments and amount (`update_entry` with `data`, so its EUR value is recomputed), keeps its own author, merchant when the draft has none, note and secrecy; the draft is soft-deleted.
- Behaviour (spec 3.5): confirming a photo or voice draft runs `find_duplicates(..., exclude_id=draft.id)`; a hint offers **Összevonás** (only for non-secret candidates the viewer can edit), **Mentés külön** and **Mégse**. Never automatic.

- [ ] **Step 1: Failing tests**

```python
def test_merge_moves_lines_photo_and_amount(adult, adult2, users): ...
def test_merge_keeps_target_author_and_hidden_flag(adult, adult2, users): ...
def test_merge_never_offers_secret_target(adult, adult2, users): ...   # hint without the merge button; POST merge -> 403
def test_merge_into_other_wallet_refused(adult, users): ...
def test_save_separately_confirms_draft(adult, users): ...
```

- [ ] **Step 2: Run, expect failures. Step 3: Implement. Step 4: Run; full suite green.**
- [ ] **Step 5: Commit** `feat(haztartas): merge a receipt draft into its duplicate`

---

### Task 10: Photo and voice capture on the phone (inline, screenshot loop)

**Files:**
- Modify: `app/static/capture.js`, `app/static/sw.js`, `app/templates/capture.html`, `app/templates/home.html`, `app/static/app.css`, `app/strings/hu.py`, `scripts/offline_check.mjs`
- Test: `tests/test_capture_routes.py` (page markup), `scripts/offline_check.mjs` (behaviour)

**Interfaces:**
- Consumes: Task 7 `POST /capture/media`.
- Behaviour:
  - Home dock: Fotó and Hang become links to `/capture#photo` and `/capture#voice` (the `soon` labels go). `/capture` shows three modes on one cached page: photo, voice, manual (the current form).
  - Photo and voice modes carry, above the shutter, the hidden toggle and, for a child only, the same wallet choice as the manual form (spec 3.4, 3.7).
  - Photo: `<input type="file" accept="image/*" capture="environment">`. On change: `BarcodeDetector({formats: ['qr_code']})` on the original image (`createImageBitmap`), absent or failing -> no QR; then downscale on a canvas to a long edge of `PHOTO_EDGE = 2400` px, `image/jpeg` quality 0.85 (spec 12: verify on a real long receipt in Task 11 and change the constant if it does not read).
  - Voice: `MediaRecorder` with a stop button and a visible seconds counter; stops itself at `MAX_RECORD_S = 120`. Format decided by the gate below.
  - Queue item: `{client_uuid, kind: 'photo'|'audio', payload: {wallet_id, hidden, date, qr, mime, user_id}, created_at, blob}`; the existing store, no `onupgradeneeded` change. `upload()` sends `FormData` to `/capture/media` for these kinds with `MEDIA_TIMEOUT_MS`, the JSON path for `manual`; the success and refusal handling stays one code path.
  - After an online capture whose answer arrives while the page is still open, go to `answer.url` (the confirm screen); otherwise show `S["capture_draft"]`. The refused list shows a photo item as "Fotó · <date>" (no thumbnail).
  - `sw.js`/`capture.js` cache name `haztartas-v4`.

- [ ] **Step 1: Voice format gate (needs the Gemini key).** Make a 10 s Hungarian speech sample (`espeak-ng -v hu` if installed on LXC 109, else ask the owner for a phone voice memo), record it through headless Chrome's `MediaRecorder` (`--use-fake-device-for-media-stream --use-file-for-fake-audio-capture=<wav>`) as `audio/webm;codecs=opus`, and run `scripts/gemini_smoke.py --audio sample.webm --mime audio/webm`. A correct transcript and fields: keep `MediaRecorder` webm. A 400 or an empty transcript: record PCM through `AudioContext` and encode a 16 kHz mono WAV in `capture.js` (`audio/wav`, on Gemini's documented list). Write the outcome and the date into the `capture.js` comment above the recorder.
- [ ] **Step 2: Failing tests**: `test_capture_page_has_photo_and_voice_modes` (input with `capture="environment"`, hidden toggle in both modes), `test_child_capture_page_offers_wallet_choice_in_photo_mode`, `test_sw_and_capture_js_share_cache_name` (reads both files, asserts `haztartas-v4` in each).
- [ ] **Step 3: Implement**, then the screenshot loop for the three modes and the recording state at 390 and 360 px.
- [ ] **Step 4: Extend `scripts/offline_check.mjs`**: offline, choose a test JPEG through `setInputFiles`, counter shows 1; online, wait, assert one draft exists with an attachment and the counter is empty; replay the 413 shape with `page.route()` and assert the item is kept as refused and not retried by the timer. Run it on a fresh database: all steps pass.
- [ ] **Step 5: Full suite green. Commit** `feat(haztartas): photo and voice capture with offline queue`

---

### Task 11: Real-key checks, deploy, docs

**Files:**
- Modify: `README.md`, `.env.example`, `docs/proxmox/56_Family_Budget_PWA.md`, `docs/superpowers/specs/2026-11-15-haztartas-design.md` (section 0), `PRODUCT.md` if it lists phases

- [ ] **Step 1: Smoke with the real key** from LXC 109: `scripts/gemini_smoke.py --photo` on one long Hungarian receipt and one Slovak receipt photographed without its QR in frame. Expect merchant, total and all lines; if the long one misreads, raise `PHOTO_EDGE` (Task 10) and repeat. Record model id, latency and `totalTokenCount` in the README.
- [ ] **Step 2: Whole-branch review** (most capable model): diff `main..haztartas-phase2`, the spec, this plan. Fix, re-run tests and `offline_check.mjs`.
- [ ] **Step 3: Ask the owner** before merge, push and deploy (outward-facing). On yes: merge to `main`, push, Komodo Pull + Deploy of `haztartas` (the compose change needs the new env passed; `pull_policy: build` rebuilds). Before deploying confirm `HAZTARTAS_GEMINI_KEY` is set in the Stack Environment (read it by name only, never print it).
- [ ] **Step 4: Post-deploy checks**: container healthy; migration 003 applied (`schema_version`), phase 1 row count unchanged; through the public URL from Slovakia, a real photo upload completes and lands on the confirm screen (time it: Pangolin must not cut a ~45 s request; if it does, that is a blocker to report, not a timeout to raise blindly); `/attachments/<id>` of a hidden test entry 404s for the other adult; delete the test entries.
- [ ] **Step 5: Phone tests by the owner** (written into the README): photo of a Slovak receipt online (eKasa path), photo of a Hungarian receipt in flight mode then reconnect (one draft appears, counter clears), voice entry, a hidden gift photo by the child (parents see only the redacted row), a recording left running stops at 2 minutes.
- [ ] **Step 6: Docs**: spec section 0 phase 2 row "deployed <date>", the plan path; `56_Family_Budget_PWA.md` gains a phase 2 section (what the reviews caught, the eKasa and Gemini paths, the billing-project rule), no family names, placeholder domain. Commit `docs(haztartas): phase 2 deployed`; push only when asked.
