# Pedikur Phase 2 Implementation Plan

> **For agentic workers: read this block before invoking any skill.** This plan
> does NOT use superpowers:subagent-driven-development, and does not use
> superpowers:executing-plans either. Every task is written inline; subagents
> review, they do not implement. The execution mode was chosen deliberately
> and is described in "Execution mode" below. Steps use checkbox (`- [ ]`)
> syntax for tracking.

**Goal:** The money side of the practice: what she buys, what it cost, what is
left on the shelf, and how much of it a treatment eats. Phase 1 already records
what comes in; this records what goes out, so phase 4 can subtract one from the
other.

**Architecture:** Four additive tables behind one migration, two new service
modules (`products`, `stock`) and one more (`expenses`), and a single new rule
in the existing close path. Stock is never stored as a number: a product's
quantity is `SUM(qty)` over its append-only movements. Consumption is posted by
reconciling a visit's ledger against its recipes on every close, so the same
code is correct on a first close, a double tap, a status bounce, and a
treatment added after the fact.

**Tech Stack:** Unchanged from phase 1. Python 3.13, FastAPI, Uvicorn,
SQLAlchemy 2.0 (`DeclarativeBase` + `Mapped[]`), Jinja2, htmx 2.x vendored,
pytest. SQLite via the stdlib driver. No npm, no bundler, no build step, and
phase 2 adds no dependency of any kind.

**Spec:** `docs/superpowers/specs/2026-09-05-pedikur-design.md` - read it before
starting, in particular section 5 (the five decisions that carry the data
model) and section 6 (Stock and Expenses). Terms in **bold** here (Product,
Treatment Recipe, Stock Movement, Visit, Visit Item) are defined in the repo
root `CONTEXT.md` under "Pedikur" and are used in their glossary sense.

**Predecessor:** `docs/superpowers/plans/2026-09-05-pedikur-phase1.md`,
implemented and deployed on 2026-09-07. The app is live on port 3010 of LXC 100
and the practitioner is using it daily. That is the single most important fact
in this plan: **every change here lands on a database with real client and
visit data in it.** Nothing may be destructive, and every migration is additive.

---

## Execution mode

Same as phase 1, and for the same reason: the tasks build on each other, so the
subagent's value here is the fresh-eyes review, not the implementation.

**Every task is implemented inline, and every task's Python and SQL diff gets a
review subagent afterwards.** Give the reviewer exactly three things and nothing
from the working conversation: the task's diff (`git show`), this task's
section of this plan, and the spec. Ask for correctness and spec compliance.
Address the findings, or record in the commit why a finding was not acted on.

Scope the reviewer to Python and SQL. Exclude `templates/` and `static/`:
appearance cannot be judged from a diff, so asking for it produces confident
noise.

**Tasks that produce a screen (3, 4, 6, 7) additionally run the screenshot loop
from phase 1 Task 3, Step 5.** Render, screenshot, look at the image, fix
`app.css`, repeat. The templates and CSS are never delegated.

Task 5 carries the most dangerous logic in the phase. A wrong reconcile posts
consumption twice, or never, and the error is silent because nobody counts
bottles against the database. Its review is not optional.

### Where to stop, and where not to

Three checkpoints. Stop, report, and wait for the human at each:

1. **After Task 1**, before Task 2. The migration runs against the live
   database at the next deploy. Show the human the exact SQL and the output of
   a dry run against a copy of the production file (Task 1, Step 6) before
   anything else is built on top of it.
2. **After Task 5**, before Task 6. This is the close path, the one screen the
   spec says must stay one tap. Show a screenshot of the close screen and the
   movements a test close produced.
3. **After Task 8**, at the deploy. Same Komodo redeploy plus revalidate
   procedure as phase 1.

Between every other task, keep going. Do not ask "shall I continue?" and do not
summarise progress between tasks. Stop only for a blocker: a failing test that
does not yield, a step in this plan that turns out to be wrong, or anything
destructive or outward-facing.

---

## Global Constraints

Every constraint from phase 1 still applies. Repeated here because a task's
implementer reads this section and not the previous plan:

- **Money is integer cents**, EUR. Never float. Column names end in `_cents`.
- **Quantities are REAL and may be fractional.** "3.4 bottles" is exactly true:
  three sealed and one part used. This is the one place a float is correct.
- **All timestamps stored UTC as ISO-8601 text** (`strftime('%Y-%m-%dT%H:%M:%SZ')`),
  rendered in `Europe/Bratislava`. The exceptions are `working_hours.start`/`end`
  and the new `expense.date`, which are wall-clock and calendar values and must
  never be timezone-converted.
- **Soft delete via `deleted_at`; archive via `archived_at`.** Nothing added in
  this phase hard-deletes a row that carries history.
- **`created_by`** on every new table: the user id as a string, or the literal
  `api`.
- **Everything committed is English**: code, comments, commit messages. All
  user-facing copy is Hungarian and lives in `app/strings/hu.py`. `tests/test_strings.py`
  fails the build if a non-ASCII character appears in a template, so no
  Hungarian text may be typed into a `.html` file.
- **No em dashes anywhere**, in code, comments, docs or UI copy. Plain hyphens.
- **Migrations are numbered SQL files**, zero padded to three digits, applied at
  startup inside one transaction by `app/migrate.py`, preceded by an automatic
  snapshot. No Alembic.
- **Tests run inside the image, never on the host**, which has neither the
  dependencies nor the Python version:

      docker build -t pedikur-dev .
      docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
        python -m pytest -p no:cacheprovider tests -q

  Baseline at the start of this phase: **255 passed**.
- **Working directory for every path in this plan** is
  `compose/proxmox-lxc-100/pedikur/` unless the path starts with `docs/`.

---

## Decisions taken before the first line of code

These were settled with the repo owner on 2026-09-12. They are written down
because each one removes work that the spec, read literally, would have
required.

**Recipes are filled in only for the expensive materials.** Lacquer, gel,
abrasive caps. Gloves and wipes get no recipe. A treatment with no recipe posts
no consumption and that is not a bug.

The consequence is load-bearing and must survive into phase 4: **the margin
figure is partial.** It counts only the products that carry a recipe. The
dashboard may not label it "fedezet" without qualification, or it will be read
as if the gloves were in it. The spec already warns that the two headline
numbers sit on different bases; this adds a third caveat to the margin side.

**She sells a product to a client occasionally.** So `product.sale_price_cents`
exists, `visit_item.kind = 'product'` is used, and the `sale` movement reason is
used. The "+ termék" control sits inside the collapsible block *below* the Done
button, never before it.

**Photos are out of scope.** No `attachment` table, no upload path, in this
phase. There is no file upload anywhere in the app today (verified: no
`UploadFile`, no `capture=`, no multipart handler), so the expense document
photo would be the first one, and it brings storage, resizing, serving,
authorisation and backup with it. A receipt photo is an accounting document,
not a number: without it the expense, the cash result and the margin are all
still exact. It arrives later, together with the visit photo, in one piece of
work.

**One expense form, with optional line items.** Typing a lacquer purchase is
money out and stock in at once. Without the link she would type every purchase
twice, and the second entry is the one that gets skipped, after which the stock
figure drifts from the shelf with nothing to notice it. The line items are also
the only source of `unit_cost_cents`, so without them the margin is empty
whatever the recipes say.

**Consumption is posted by reconciliation, not by a first-close guard.**
See Task 5 for the full argument. In short: reconciling is idempotent by
arithmetic rather than by a flag, so it is correct in four cases where the
`closed_at` guard is correct in three.

---

## Deviations from the spec, and why

Each of these contradicts a line in
`docs/superpowers/specs/2026-09-05-pedikur-design.md` section 5. They are
deliberate. Anyone reviewing a diff against the spec will find them, so they are
named here rather than discovered there.

**1. `product` gets `archived_at` but no `active` column.** The spec lists both.
Two flags for one idea drift, and the second one is always the one somebody
forgets to check. `archived_at` is the pattern the client screen already uses
and the practitioner has already learned its two buttons ("Archiválás" and
"Visszahozás"). `treatment.active` stays as it is; it is not worth a migration
on live data to make two tables agree on a spelling.

**2. `product` gains `sale_price_cents`, which the spec does not list.** Forced
by the decision above that she occasionally sells. Nullable: NULL means "not for
sale", and the close screen's product list filters on it.

**3. No foreign key is added to `visit_item.product_id`.** The column exists
from migration 001 with a `-- phase 2` comment and a CHECK that already
guarantees exactly one of `treatment_id` / `product_id` is set, but no
`REFERENCES`. Adding one now means SQLite's 12-step table rebuild, and
`PRAGMA foreign_keys` cannot be changed inside a transaction, which is exactly
where `migrate.py` runs every script. The column is written only by
`app.services.visits`, which looks the product up first, and products are never
deleted, only archived, so nothing can dangle. Recorded as a known,
service-enforced invariant instead of a database one.

**4. `expense.category` stores ASCII keys, not the Hungarian labels.** The spec
gives the list as "Anyag, Eszkoz, Berleti dij, Rezsi, Marketing, Egyeb". Stored
as `anyag`, `eszkoz`, `berleti_dij`, `rezsi`, `marketing`, `egyeb`, with the
accented labels in `app/strings/hu.py`. The CHECK constraint then contains no
text anyone might want to reword, and the copy stays in the one file
`tests/test_strings.py` polices.

---

## Out of scope for phase 2

Named so they are decisions, not omissions: the `attachment` table and every
photo path, Google sync, buffers, free slot highlighting, the dashboard, the
Recall List, the MCP server, and any `/api/*` route for products, stock or
expenses. The API surface stays exactly the five routes phase 1 shipped; nothing
outside the app needs to write stock yet, and an unused endpoint is an unguarded
one.

---

## File Structure

```
compose/proxmox-lxc-100/pedikur/
  app/
    migrations/
      004_phase2.sql          product, treatment_recipe, expense, stock_movement
    models.py                 + Product, TreatmentRecipe, StockMovement, Expense
    services/
      products.py             NEW  the catalogue: create, list, archive
      stock.py                NEW  quantity as a SUM, append-only movements,
                                   and the visit reconcile
      recipes.py              NEW  treatment -> product yield
      expenses.py             NEW  expense + its optional inbound lines
      visits.py               MOD  close/set_status call the reconcile;
                                   add_product; remove_treatment -> remove_item;
                                   total_cents moved in from the API router
    routers/
      stock.py                NEW  /stock
      expenses.py             NEW  /expenses
      settings.py             MOD  /settings/treatments/{id}/recipe
      visits.py               MOD  the item remove path, + product
      api.py                  MOD  uses visits.total_cents
    templates/
      stock.html              NEW
      expenses.html           NEW
      settings_recipe.html    NEW
      settings_index.html     MOD  two more links
      settings_treatments.html MOD a link per treatment to its recipe
      visit_close.html        MOD  product lines, + termék, a total
    strings/hu.py             MOD
    main.py                   MOD  include the two new routers
  tests/
    test_products.py          NEW
    test_stock.py             NEW
    test_recipes.py           NEW
    test_expenses.py          NEW
    test_stock_routes.py      NEW
    test_expenses_routes.py   NEW
    test_visits.py            MOD  the reconcile cases
    test_visits_routes.py     MOD  selling a product at close
```

---

### Task 1: The schema

**Files:**
- Create: `app/migrations/004_phase2.sql`
- Modify: `app/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `app.migrate.run`, `app.db.Database`, the existing `Base`.
- Produces: `models.Product`, `models.TreatmentRecipe`, `models.StockMovement`,
  `models.Expense`. Every one of them mirrors a table in `004_phase2.sql`; the
  SQL is the schema of record and the classes follow it, never the other way
  round.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py - append to the existing file
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Expense, Product, StockMovement, TreatmentRecipe


def test_a_product_starts_with_no_stock_and_no_sale_price(db):
    with db.session() as s:
        p = Product(name="Lakk", unit="flakon", min_stock=2,
                    created_by="1", created_at="2026-09-12T08:00:00Z")
        s.add(p)
        s.flush()
        assert p.sale_price_cents is None
        assert p.archived_at is None


def test_a_movement_of_zero_is_refused(db):
    """A reconcile that decided nothing changed must write no row at all.
    Without this CHECK it would leave a trail of zero rows that look like
    activity and are not."""
    with pytest.raises(IntegrityError):
        with db.session() as s:
            p = Product(name="Lakk", unit="flakon", created_by="1",
                        created_at="2026-09-12T08:00:00Z")
            s.add(p)
            s.flush()
            s.add(StockMovement(product_id=p.id, qty=0, reason="correction",
                                created_by="1",
                                created_at="2026-09-12T08:00:00Z"))


def test_an_invented_movement_reason_is_refused(db):
    with pytest.raises(IntegrityError):
        with db.session() as s:
            p = Product(name="Lakk", unit="flakon", created_by="1",
                        created_at="2026-09-12T08:00:00Z")
            s.add(p)
            s.flush()
            s.add(StockMovement(product_id=p.id, qty=1, reason="ajandek",
                                created_by="1",
                                created_at="2026-09-12T08:00:00Z"))


def test_a_recipe_that_yields_nothing_is_refused(db):
    """Consumption is 1/treatments_per_unit. A zero here is a
    ZeroDivisionError inside the close path, with a client in the chair.

    The treatment is created rather than referenced by a made-up id: with
    PRAGMA foreign_keys = ON a dangling treatment_id raises the same
    IntegrityError, and the test would pass without the CHECK ever firing.
    """
    from app.models import Treatment
    with pytest.raises(IntegrityError):
        with db.session() as s:
            t = Treatment(name="Pedikur", duration_min=45, price_cents=2500,
                          created_by="1")
            p = Product(name="Lakk", unit="flakon", created_by="1",
                        created_at="2026-09-12T08:00:00Z")
            s.add_all([t, p])
            s.flush()
            s.add(TreatmentRecipe(treatment_id=t.id, product_id=p.id,
                                  treatments_per_unit=0))


def test_an_invented_expense_category_is_refused(db):
    with pytest.raises(IntegrityError):
        with db.session() as s:
            s.add(Expense(date="2026-09-12", category="kave",
                          amount_cents=500, created_by="1",
                          created_at="2026-09-12T08:00:00Z"))


def test_an_expense_date_has_to_be_a_calendar_date(db):
    with pytest.raises(IntegrityError):
        with db.session() as s:
            s.add(Expense(date="2026-09-12T08:00:00Z", category="anyag",
                          amount_cents=500, created_by="1",
                          created_at="2026-09-12T08:00:00Z"))
```

If `tests/test_models.py` has no `db` fixture, copy the one from
`tests/test_treatments.py`:

```python
@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)
```

- [ ] **Step 2: Run it to verify it fails**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests/test_models.py -q

Expected: FAIL, `ImportError: cannot import name 'Product' from 'app.models'`

- [ ] **Step 3: Write `app/migrations/004_phase2.sql`**

```sql
-- Phase 2: products, treatment recipes, stock movements and expenses.
--
-- Table order matters. stock_movement references expense, so expense is
-- created first: SQLite would accept the other order and only fail at the
-- first insert, which is a far worse place to find out.
--
-- No foreign key is added to visit_item.product_id. The column was left
-- FK-less in 001 on purpose, and adding one now means SQLite's 12-step table
-- rebuild. PRAGMA foreign_keys cannot be changed inside a transaction, and
-- migrate.py runs every script inside one. The column is written only by
-- app/services/visits.py, which looks the product up first, and a product is
-- never deleted, only archived, so nothing can dangle.

CREATE TABLE product (
    id               INTEGER PRIMARY KEY,
    name             TEXT    NOT NULL,
    -- Free text, and whatever she buys and counts: flakon, tekercs, doboz,
    -- par, db. Never a unit that would need converting, because the receipt
    -- says "one bottle, EUR 12" and converting it to millilitres is her
    -- arithmetic to do at every single purchase.
    unit             TEXT    NOT NULL,
    min_stock        REAL    NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
    -- NULL for anything she only consumes; set for the few she resells.
    sale_price_cents INTEGER CHECK (sale_price_cents IS NULL
                                    OR typeof(sale_price_cents) = 'integer'),
    -- No `active` column next to this one. The spec lists both; two flags for
    -- one idea drift, and the archive/unarchive pair is what the client
    -- screen already uses and she has already learned.
    archived_at      TEXT,
    created_by       TEXT    NOT NULL,
    created_at       TEXT    NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX idx_product_name ON product (name);

CREATE TABLE treatment_recipe (
    id                  INTEGER PRIMARY KEY,
    treatment_id        INTEGER NOT NULL REFERENCES treatment (id),
    product_id          INTEGER NOT NULL REFERENCES product (id),
    -- How many Treatments one unit lasts for, because nobody knows they use
    -- 0.4 ml of lacquer and everybody knows a bottle gives about thirty
    -- fills. Consumption is stored as 1/this, so it can never be zero.
    treatments_per_unit REAL    NOT NULL CHECK (treatments_per_unit > 0),
    -- One row per pair. Two rows for the same product on the same treatment
    -- would double its consumption and nothing downstream would say why.
    UNIQUE (treatment_id, product_id)
);

CREATE TABLE expense (
    id           INTEGER PRIMARY KEY,
    -- A calendar date, like working_hours.date, not an instant. A receipt is
    -- dated, not timestamped, and converting it to UTC moves half of them
    -- across midnight into the wrong month.
    date         TEXT NOT NULL
                 CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    vendor       TEXT,
    -- ASCII keys, never the Hungarian labels. The labels live in
    -- app/strings/hu.py; free text here would give the dashboard four
    -- spellings of one category within two months.
    category     TEXT NOT NULL CHECK (category IN
                 ('anyag', 'eszkoz', 'berleti_dij', 'rezsi',
                  'marketing', 'egyeb')),
    amount_cents INTEGER NOT NULL CHECK (typeof(amount_cents) = 'integer'),
    note         TEXT,
    deleted_at   TEXT,
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX idx_expense_date ON expense (date);

CREATE TABLE stock_movement (
    id              INTEGER PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES product (id),
    -- Signed: positive is stock in, negative is stock out. Never zero, or a
    -- reconcile that decided nothing had changed would still leave a row
    -- behind that reads as activity.
    qty             REAL    NOT NULL CHECK (qty <> 0),
    -- The real price on an inbound movement, the last known purchase price at
    -- that moment on an outbound one. Snapshotted exactly the way
    -- visit_item.unit_price_cents is: without it, buying the same lacquer
    -- dearer in June would silently rewrite January's margin, which is the
    -- defect the revenue side was designed to avoid.
    unit_cost_cents INTEGER NOT NULL DEFAULT 0
                    CHECK (typeof(unit_cost_cents) = 'integer'),
    reason          TEXT    NOT NULL CHECK (reason IN
                    ('purchase', 'opening', 'consumption', 'sale',
                     'correction', 'waste')),
    visit_id        INTEGER REFERENCES visit (id),
    expense_id      INTEGER REFERENCES expense (id),
    note            TEXT,
    created_by      TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
        DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
-- There is no current_stock column anywhere: a product's quantity is
-- SUM(qty) over these rows, so this index is the entire stock screen.
CREATE INDEX idx_stock_movement_product ON stock_movement (product_id);
-- The close path reconciles one visit at a time, and only visit-linked rows
-- take part. Partial, because most rows have no visit_id at all.
CREATE INDEX idx_stock_movement_visit ON stock_movement (visit_id)
    WHERE visit_id IS NOT NULL;
```

- [ ] **Step 4: Add the models**

In `app/models.py`, change the module docstring first - it currently says
"Phase 1 tables":

```python
"""The tables. The schema of record is app/migrations/*.sql; these classes
mirror it and must be changed together with a new migration.
"""
```

Then append, after `Setting`:

```python
class Product(Base):
    __tablename__ = "product"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String)
    min_stock: Mapped[float] = mapped_column(Float, default=0)
    sale_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class TreatmentRecipe(Base):
    __tablename__ = "treatment_recipe"
    id: Mapped[int] = mapped_column(primary_key=True)
    treatment_id: Mapped[int] = mapped_column(ForeignKey("treatment.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    treatments_per_unit: Mapped[float] = mapped_column(Float)

    product: Mapped[Product] = relationship(lazy="joined")
    treatment: Mapped[Treatment] = relationship(lazy="joined")


class Expense(Base):
    __tablename__ = "expense"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(String)
    vendor: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String)
    amount_cents: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class StockMovement(Base):
    """Append-only. Nothing in the codebase may edit or delete one of these
    rows: a correction is another row, and that is the whole point of holding
    the quantity as a sum rather than a column."""
    __tablename__ = "stock_movement"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    qty: Mapped[float] = mapped_column(Float)
    unit_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(String)
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visit.id"), nullable=True)
    expense_id: Mapped[int | None] = mapped_column(
        ForeignKey("expense.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)

    product: Mapped[Product] = relationship(lazy="joined")
```

`Float` and `Text` are already imported at the top of `models.py`; `ForeignKey`,
`Integer`, `String`, `relationship` and `Mapped` likewise. No import line
changes.

- [ ] **Step 5: Run the tests to verify they pass**

Run:

    docker build -t pedikur-dev . && \
    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests -q

Expected: PASS, 261 tests (255 + 6).

- [ ] **Step 6: Dry run the migration against a copy of the live database**

This is the checkpoint. The migration will run against real data at the next
deploy, so prove it here first. Nothing below writes to the live file.

```bash
ssh root@192.168.0.110 \
  'sqlite3 /srv/docker-data/pedikur/db.sqlite ".backup /tmp/pedikur-dryrun.sqlite"'
scp root@192.168.0.110:/tmp/pedikur-dryrun.sqlite /tmp/pedikur-dryrun.sqlite
ssh root@192.168.0.110 'rm -f /tmp/pedikur-dryrun.sqlite'
```

`.backup` rather than `cp`: the database is in WAL mode and a plain copy of the
main file without its `-wal` sidecar loses every write since the last
checkpoint.

Then apply the migration to the copy and check the schema and the row counts:

```bash
mkdir -p /tmp/pedikur-dryrun && cp /tmp/pedikur-dryrun.sqlite /tmp/pedikur-dryrun/db.sqlite
docker run --rm --user 0 -v "$PWD":/srv -v /tmp/pedikur-dryrun:/data -w /srv \
  pedikur-dev python -c "
from pathlib import Path
from app import migrate
print(migrate.run(Path('/data/db.sqlite'), backup_dir=Path('/data/backup')))
"
sqlite3 /tmp/pedikur-dryrun/db.sqlite \
  "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;
   SELECT 'clients', COUNT(*) FROM client;
   SELECT 'visits', COUNT(*) FROM visit;
   PRAGMA foreign_key_check;"
```

Expected: `['004_phase2.sql']`, the four new tables present, the client and
visit counts unchanged from before, and `foreign_key_check` silent.

```bash
rm -rf /tmp/pedikur-dryrun /tmp/pedikur-dryrun.sqlite
```

**Rollback, if the dry run goes wrong:** nothing to roll back. The live
database was never touched, only a `.backup` copy in `/tmp` on the host and a
copy under `/tmp` here, both deleted by the line above. Fix the SQL and dry run
again.

- [ ] **Step 7: Commit**

```bash
git add app/migrations/004_phase2.sql app/models.py tests/test_models.py
git commit -m "feat(pedikur): the phase 2 tables - products, recipes, stock, expenses"
```

- [ ] **Step 8: STOP.** Report to the human: the migration SQL, the dry run
output, and the new test count. Wait for a yes before Task 2.

---

### Task 2: Products and the stock ledger

**Files:**
- Create: `app/services/products.py`
- Create: `app/services/stock.py`
- Test: `tests/test_products.py`, `tests/test_stock.py`

**Interfaces:**
- Consumes: `models.Product`, `models.StockMovement`, `app.db.fold`,
  `app.services.timeutil.local_now` and `to_utc_iso`.
- Produces:
  - `products.list_all(session, include_archived=False) -> list[Product]`
  - `products.for_sale(session) -> list[Product]`
  - `products.get(session, product_id) -> Product` (raises `LookupError`)
  - `products.create(session, name, unit, created_by, min_stock=0.0, sale_price_cents=None) -> Product`
  - `products.update(session, product_id, **fields) -> Product`
  - `products.archive(session, product_id) -> None`, `products.unarchive(session, product_id) -> None`
  - `stock.record(session, product_id, qty, reason, created_by, unit_cost_cents=0, visit_id=None, expense_id=None, note=None) -> StockMovement`
  - `stock.quantity(session, product_id) -> float`
  - `stock.last_cost_cents(session, product_id) -> int`
  - `stock.levels(session, include_archived=False) -> list[stock.Level]`
  - `stock.Level` is a frozen dataclass with `.product`, `.qty` and a
    `.below_min` property.
  - `stock.REASONS`, `stock.MANUAL_REASONS`, `stock.QTY_EPSILON`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_products.py
import pytest

from app import migrate
from app.db import Database
from app.services import products


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


def test_create_and_list(db):
    with db.session() as s:
        products.create(s, "Lakk", "flakon", created_by="1", min_stock=2)
        products.create(s, "Kesztyu", "doboz", created_by="1")
    with db.session() as s:
        assert [p.name for p in products.list_all(s)] == ["Kesztyu", "Lakk"]


def test_archived_products_are_out_unless_asked_for(db):
    with db.session() as s:
        gone = products.create(s, "Regi lakk", "flakon", created_by="1")
        products.create(s, "Lakk", "flakon", created_by="1")
        products.archive(s, gone.id)
    with db.session() as s:
        assert [p.name for p in products.list_all(s)] == ["Lakk"]
        assert len(products.list_all(s, include_archived=True)) == 2


def test_unarchive_brings_it_back(db):
    with db.session() as s:
        p = products.create(s, "Lakk", "flakon", created_by="1")
        products.archive(s, p.id)
        products.unarchive(s, p.id)
    with db.session() as s:
        assert [p.name for p in products.list_all(s)] == ["Lakk"]


def test_only_products_with_a_sale_price_are_for_sale(db):
    with db.session() as s:
        products.create(s, "Lakk", "flakon", created_by="1")
        products.create(s, "Krem", "tubus", created_by="1",
                        sale_price_cents=850)
    with db.session() as s:
        assert [p.name for p in products.for_sale(s)] == ["Krem"]


def test_an_archived_product_is_never_for_sale(db):
    with db.session() as s:
        p = products.create(s, "Krem", "tubus", created_by="1",
                            sale_price_cents=850)
        products.archive(s, p.id)
    with db.session() as s:
        assert products.for_sale(s) == []


def test_a_product_needs_a_name_and_a_unit(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            products.create(s, "   ", "flakon", created_by="1")
        with pytest.raises(ValueError):
            products.create(s, "Lakk", "  ", created_by="1")


def test_update_refuses_a_field_that_is_not_on_the_whitelist(db):
    """Field names reach update from a form. Without the whitelist,
    ?created_by=... or ?id=... would be an accepted write."""
    with db.session() as s:
        p = products.create(s, "Lakk", "flakon", created_by="1")
        with pytest.raises(ValueError):
            products.update(s, p.id, created_by="2")
```

```python
# tests/test_stock.py
import pytest

from app import migrate
from app.db import Database
from app.services import products, stock


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


@pytest.fixture
def lakk(db):
    with db.session() as s:
        return products.create(s, "Lakk", "flakon", created_by="1",
                               min_stock=2).id


def test_quantity_is_the_sum_of_the_movements(db, lakk):
    with db.session() as s:
        stock.record(s, lakk, 3, "opening", created_by="1",
                     unit_cost_cents=1200)
        stock.record(s, lakk, 2, "purchase", created_by="1",
                     unit_cost_cents=1300)
        stock.record(s, lakk, -1, "waste", created_by="1")
    with db.session() as s:
        assert stock.quantity(s, lakk) == pytest.approx(4.0)


def test_a_product_with_no_movements_has_no_stock(db, lakk):
    """None from SUM() must not reach a template as None: the level screen
    would render "None flakon" and the below_min comparison would raise."""
    with db.session() as s:
        assert stock.quantity(s, lakk) == 0.0


def test_stock_may_go_negative(db, lakk):
    """Deliberate. Blocking it would mean a "nincs eleg lakk" error in the
    middle of closing a visit with the client in the chair, which is the day
    she stops using the app."""
    with db.session() as s:
        stock.record(s, lakk, -1, "consumption", created_by="1")
    with db.session() as s:
        assert stock.quantity(s, lakk) == pytest.approx(-1.0)


def test_the_level_list_flags_what_is_under_the_minimum(db, lakk):
    with db.session() as s:
        stock.record(s, lakk, 1, "opening", created_by="1")
    with db.session() as s:
        level = stock.levels(s)[0]
        assert level.qty == pytest.approx(1.0)
        assert level.below_min is True


def test_the_level_list_does_not_flag_what_is_exactly_at_the_minimum(db, lakk):
    with db.session() as s:
        stock.record(s, lakk, 2, "opening", created_by="1")
    with db.session() as s:
        assert stock.levels(s)[0].below_min is False


def test_the_level_list_covers_a_product_with_no_movements(db, lakk):
    with db.session() as s:
        levels = stock.levels(s)
        assert len(levels) == 1
        assert levels[0].qty == 0.0


def test_the_cost_to_charge_is_the_price_of_the_last_purchase(db, lakk):
    with db.session() as s:
        stock.record(s, lakk, 3, "opening", created_by="1",
                     unit_cost_cents=1200)
        stock.record(s, lakk, 2, "purchase", created_by="1",
                     unit_cost_cents=1500)
        # An outbound movement must not become the "last known price"
        stock.record(s, lakk, -1, "consumption", created_by="1",
                     unit_cost_cents=1500)
    with db.session() as s:
        assert stock.last_cost_cents(s, lakk) == 1500


def test_the_cost_is_zero_when_nothing_was_ever_bought(db, lakk):
    """Zero, not an exception. A consumption posted at zero cost is a missing
    margin; a raised exception is a failed close."""
    with db.session() as s:
        assert stock.last_cost_cents(s, lakk) == 0


def test_a_movement_of_zero_is_refused_before_it_reaches_the_database(db, lakk):
    with db.session() as s:
        with pytest.raises(ValueError):
            stock.record(s, lakk, 0, "correction", created_by="1")


def test_an_invented_reason_is_refused_before_it_reaches_the_database(db, lakk):
    with db.session() as s:
        with pytest.raises(ValueError):
            stock.record(s, lakk, 1, "ajandek", created_by="1")
```

- [ ] **Step 2: Run them to verify they fail**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests/test_products.py tests/test_stock.py -q

Expected: FAIL, `ImportError: cannot import name 'products' from 'app.services'`

- [ ] **Step 3: Write `app/services/products.py`**

```python
"""The Product catalogue: the things she buys, counts, and sometimes resells.

A Product is a bottle, a roll, a box, never millilitres, because the receipt
says "one bottle, EUR 12" and converting it is her arithmetic to do at every
purchase.

There is no `active` flag next to `archived_at`. The spec lists both; two
flags for one idea drift, and the archive/unarchive pair is the one the client
screen already uses.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product
from app.services import timeutil

# Field names arrive from a form, so update() writes only these. Without the
# whitelist a crafted field would reach created_by, archived_at or id.
_FIELDS = frozenset({"name", "unit", "min_stock", "sale_price_cents"})


def _by_name():
    """SQLite's BINARY collation sorts every accented initial after Z, so a
    name starting with one lands below every unaccented name. fold() is the
    same UDF the client and treatment lists use."""
    return func.fold(Product.name)


def list_all(session: Session, include_archived: bool = False) -> list[Product]:
    stmt = select(Product)
    if not include_archived:
        stmt = stmt.where(Product.archived_at.is_(None))
    return list(session.scalars(stmt.order_by(_by_name())))


def for_sale(session: Session) -> list[Product]:
    """The products that may be added to a Visit. sale_price_cents IS NULL
    means "I only use this", and an archived product is off every list."""
    return list(session.scalars(
        select(Product)
        .where(Product.archived_at.is_(None),
               Product.sale_price_cents.isnot(None))
        .order_by(_by_name())))


def get(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if product is None:
        raise LookupError(f"no product {product_id}")
    return product


def create(session: Session, name: str, unit: str, created_by: str,
           min_stock: float = 0.0,
           sale_price_cents: int | None = None) -> Product:
    name, unit = name.strip(), unit.strip()
    if not name:
        raise ValueError("a product needs a name")
    if not unit:
        # An empty unit renders as a bare number on the stock screen, and she
        # cannot tell three bottles from three millilitres.
        raise ValueError("a product needs a unit")
    if float(min_stock) < 0:
        raise ValueError("a minimum stock cannot be negative")
    product = Product(name=name, unit=unit, min_stock=float(min_stock),
                      sale_price_cents=sale_price_cents, created_by=created_by,
                      created_at=timeutil.to_utc_iso(timeutil.local_now()))
    session.add(product)
    session.flush()
    return product


def update(session: Session, product_id: int, **fields) -> Product:
    bad = set(fields) - _FIELDS
    if bad:
        raise ValueError(f"not an editable product field: {sorted(bad)}")
    product = get(session, product_id)
    for key, value in fields.items():
        setattr(product, key, value)
    session.flush()
    return product


def archive(session: Session, product_id: int) -> None:
    """Off the lists, all its movements kept. Products are never deleted:
    historical Stock Movements and Visit Items point at them."""
    get(session, product_id).archived_at = \
        timeutil.to_utc_iso(timeutil.local_now())
    session.flush()


def unarchive(session: Session, product_id: int) -> None:
    get(session, product_id).archived_at = None
    session.flush()
```

- [ ] **Step 4: Write `app/services/stock.py`**

Leave out `reconcile_visit` for now; it arrives in Task 5 with its own tests.

```python
"""Stock is a sum, not a stored number.

There is no current_stock column anywhere: a Product's quantity is SUM(qty)
over its Stock Movements. Instant at this scale, and it removes the class of
bug where the movements and the stored figure drift apart with nothing to
notice it.

Movements are append-only. Nothing in this module edits or deletes a row. A
correction is another row, a mistake is another row, and undoing an expense is
another row. That rule is what makes the sum trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Product, StockMovement
from app.services import products, timeutil

REASONS = ("purchase", "opening", "consumption", "sale", "correction", "waste")
# What a human may pick on the stock screen. purchase belongs to the expense
# form, where it is typed once together with the money; consumption and sale
# are posted by the close path and must never be typed by hand, or the ledger
# would carry two entries for one bottle.
MANUAL_REASONS = ("opening", "correction", "waste")
# Anything that puts stock on the shelf, and therefore carries a real price.
INBOUND = ("purchase", "opening")

# Quantities are floats on purpose: a third of a bottle is a third of a
# bottle. The price of that is that a sum computed in Python and the same sum
# computed by SQLite can differ in the last bit, so the reconcile in this
# module compares against this rather than against zero.
QTY_EPSILON = 1e-9


@dataclass(frozen=True)
class Level:
    product: Product
    qty: float

    @property
    def below_min(self) -> bool:
        """Strictly below. Exactly at the minimum is not yet a warning, or the
        screen is orange on the day she restocks to precisely min_stock."""
        return self.qty < self.product.min_stock


def record(session: Session, product_id: int, qty: float, reason: str,
           created_by: str, unit_cost_cents: int = 0,
           visit_id: int | None = None, expense_id: int | None = None,
           note: str | None = None) -> StockMovement:
    """Append one movement. Positive puts stock on the shelf, negative takes
    it off.

    Both guards are also CHECK constraints in 004_phase2.sql. They are
    repeated here because an IntegrityError surfaces at commit, by which time
    the route has left its try block and the user sees a 500 instead of a
    message.
    """
    if reason not in REASONS:
        raise ValueError(f"not a stock movement reason: {reason!r}")
    if abs(float(qty)) < QTY_EPSILON:
        raise ValueError("a stock movement of zero is not a movement")
    products.get(session, product_id)   # LookupError rather than IntegrityError
    movement = StockMovement(
        product_id=product_id, qty=float(qty), reason=reason,
        unit_cost_cents=int(unit_cost_cents), visit_id=visit_id,
        expense_id=expense_id, note=note, created_by=created_by,
        created_at=timeutil.to_utc_iso(timeutil.local_now()))
    session.add(movement)
    session.flush()
    return movement


def quantity(session: Session, product_id: int) -> float:
    """SUM over an empty set is NULL, which would reach a template as None and
    render "None flakon"."""
    total = session.scalar(
        select(func.sum(StockMovement.qty))
        .where(StockMovement.product_id == product_id))
    return float(total or 0.0)


def last_cost_cents(session: Session, product_id: int) -> int:
    """What to charge an outbound movement with: the price of the most recent
    inbound one.

    Zero when nothing was ever bought, rather than an exception. A consumption
    posted at zero cost is a missing margin on one line; a raised exception is
    a failed close with a client in the chair. The stock screen shows which
    products have no price so the gap is visible rather than silent.

    Ordered by id as well as created_at: two movements written inside one
    transaction share a timestamp to the second, and the tie has to break
    towards the later row.
    """
    row = session.scalars(
        select(StockMovement)
        .where(StockMovement.product_id == product_id,
               StockMovement.reason.in_(INBOUND))
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(1)).first()
    return row.unit_cost_cents if row is not None else 0


def levels(session: Session, include_archived: bool = False) -> list[Level]:
    """Every product with its computed quantity. Two queries, not one per
    product: at a few dozen products the N+1 would not be slow, but the shape
    is what gets copied into the dashboard later, where it would be."""
    sums = dict(session.execute(
        select(StockMovement.product_id, func.sum(StockMovement.qty))
        .group_by(StockMovement.product_id)).all())
    return [Level(product=p, qty=float(sums.get(p.id) or 0.0))
            for p in products.list_all(session, include_archived)]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests -q

Expected: PASS, 279 tests (261 + 18).

- [ ] **Step 6: Commit**

```bash
git add app/services/products.py app/services/stock.py \
        tests/test_products.py tests/test_stock.py
git commit -m "feat(pedikur): products, and a stock figure that is a sum rather than a column"
```

---

### Task 3: The stock screen

**Files:**
- Create: `app/routers/stock.py`
- Create: `app/templates/stock.html`
- Modify: `app/main.py` (include the router)
- Modify: `app/templates/settings_index.html`
- Modify: `app/strings/hu.py`
- Test: `tests/test_stock_routes.py`

**Interfaces:**
- Consumes: `products.*`, `stock.levels`, `stock.record`, `stock.MANUAL_REASONS`,
  `treatments.parse_price`, `security.require_user`.
- Produces: the routes `GET /stock`, `POST /stock/products`,
  `POST /stock/{product_id}/movement`, `POST /stock/{product_id}/archive`,
  `POST /stock/{product_id}/unarchive`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_stock_routes.py
from app.services import products, stock


def _product(client, name="Lakk", unit="flakon", **kw):
    with client.app.state.db.session() as s:
        return products.create(s, name, unit, created_by="1", **kw).id


def test_the_stock_screen_needs_a_login(client):
    assert client.get("/stock").status_code in (303, 307)


def test_a_new_product_can_be_created_with_its_opening_stock(logged_in):
    r = logged_in.post("/stock/products", data={
        "name": "Lakk", "unit": "flakon", "min_stock": "2",
        "opening_qty": "3", "opening_cost_eur": "12,50"})
    assert r.status_code == 303
    with logged_in.app.state.db.session() as s:
        level = stock.levels(s)[0]
        assert level.product.name == "Lakk"
        assert level.qty == 3.0
        # The opening cost is what every later consumption is charged at
        assert stock.last_cost_cents(s, level.product.id) == 1250


def test_a_new_product_without_an_opening_quantity_writes_no_movement(logged_in):
    logged_in.post("/stock/products",
                   data={"name": "Lakk", "unit": "flakon", "min_stock": "0",
                         "opening_qty": "", "opening_cost_eur": ""})
    with logged_in.app.state.db.session() as s:
        assert stock.levels(s)[0].qty == 0.0


def test_a_mistyped_opening_price_does_not_create_a_half_product(logged_in):
    """Either the product and its opening movement both exist, or neither
    does. A product created with a silently dropped opening quantity is worse
    than a refused form: nothing says the stock is wrong."""
    r = logged_in.post("/stock/products", data={
        "name": "Lakk", "unit": "flakon", "min_stock": "0",
        "opening_qty": "3", "opening_cost_eur": "tizenketto"})
    assert r.status_code == 303
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert products.list_all(s) == []


def test_a_waste_movement_takes_stock_off_the_shelf(logged_in):
    pid = _product(logged_in)
    logged_in.post(f"/stock/{pid}/movement",
                   data={"qty": "3", "reason": "opening", "cost_eur": "12,00"})
    logged_in.post(f"/stock/{pid}/movement",
                   data={"qty": "1", "reason": "waste", "cost_eur": ""})
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, pid) == 2.0


def test_a_correction_may_be_negative(logged_in):
    pid = _product(logged_in)
    logged_in.post(f"/stock/{pid}/movement",
                   data={"qty": "-2", "reason": "correction", "cost_eur": ""})
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, pid) == -2.0


def test_consumption_cannot_be_typed_by_hand(logged_in):
    """It is posted by the close path. Allowing it here would let one bottle
    be counted twice, once by her and once by the app."""
    pid = _product(logged_in)
    r = logged_in.post(f"/stock/{pid}/movement",
                       data={"qty": "1", "reason": "consumption",
                             "cost_eur": ""})
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, pid) == 0.0


def test_archiving_a_product_takes_it_off_the_screen(logged_in):
    pid = _product(logged_in)
    logged_in.post(f"/stock/{pid}/archive")
    assert "Lakk" not in logged_in.get("/stock").text
    assert "Lakk" in logged_in.get("/stock?archived=true").text
    logged_in.post(f"/stock/{pid}/unarchive")
    assert "Lakk" in logged_in.get("/stock").text


def test_a_stale_product_id_reloads_the_screen_rather_than_crashing(logged_in):
    r = logged_in.post("/stock/9999/archive")
    assert r.status_code == 303
    assert logged_in.get("/stock").status_code == 200
```

- [ ] **Step 2: Run it to verify it fails**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests/test_stock_routes.py -q

Expected: FAIL, every test 404 or 405, because `/stock` does not exist.

- [ ] **Step 3: Add the strings**

In `app/strings/hu.py`, before the closing brace:

```python
    "stock_title": "Készlet",
    "stock_none": "Még nincs termék",
    "stock_new": "Új termék",
    "product_name": "Név",
    "product_unit": "Egység",
    "product_unit_hint": "flakon, tekercs, doboz, pár, db",
    "product_min_stock": "Minimum készlet",
    "product_sale_price": "Eladási ár, ha árulja is",
    "opening_qty": "Nyitókészlet",
    "opening_cost": "Egységár",
    "stock_low": "Kevés",
    "stock_no_price": "Nincs ára",
    "stock_movement": "Mozgás",
    "stock_qty": "Mennyiség",
    "stock_reason": "Mi történt",
    "stock_reason_opening": "Nyitókészlet",
    "stock_reason_correction": "Korrekció",
    "stock_reason_waste": "Selejt",
    "stock_reason_purchase": "Beszerzés",
    "stock_reason_consumption": "Felhasználás",
    "stock_reason_sale": "Eladás",
    "stock_qty_invalid": "A mennyiség nem szám.",
    "stock_qty_zero": "A nulla nem mozgás.",
    "stock_cost_invalid": "Az egységár nem jó.",
    "stock_reason_invalid": "Ezt a mozgást nem lehet kézzel felvenni.",
    "product_name_required": "A terméknek kell egy név.",
    "product_unit_required": "A terméknek kell egy egység.",
    "show_archived_products": "Archiváltak is",
```

Also add a `settings_stock` key next to the existing `settings_treatments` and
`settings_hours` keys:

```python
    "settings_stock": "Készlet",
```

`stock_reason_purchase`, `_consumption` and `_sale` are not offered on the form
but are needed to label a movement wherever one is displayed.

- [ ] **Step 4: Write `app/routers/stock.py`**

```python
"""The stock screen: what is on the shelf, and the three movements a human may
type. purchase comes from the expense form and consumption and sale from the
close path, so neither is offered here."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.services import products, stock, treatments
from app.strings.hu import S

router = APIRouter(prefix="/stock")

# A whitelist, not a bare S lookup: the value comes from the query string, so
# S.get(error) would let ?error=weekdays render the repr of a Python list.
_ERRORS = frozenset({
    "stock_qty_invalid", "stock_qty_zero", "stock_cost_invalid",
    "stock_reason_invalid", "product_name_required", "product_unit_required",
})

MAX_QTY = 100_000   # a pedicure practice, not a warehouse


def parse_qty(text: str) -> float:
    """"3", "3,5" or "-2" -> a float. Decimal first, so "1e999" and "nan"
    cannot reach float() and become inf."""
    cleaned = (text or "").strip().replace(",", ".")
    if not cleaned:
        raise ValueError("empty quantity")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"not a quantity: {text!r}") from None
    if not value.is_finite() or abs(value) > MAX_QTY:
        raise ValueError(f"quantity out of range: {text!r}")
    return float(value)


def _error(key: str | None) -> str | None:
    return S[key] if key in _ERRORS else None


@router.get("")
def index(request: Request, error: str | None = None, archived: bool = False,
          user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        levels = stock.levels(s, include_archived=archived)
        # Which products have never been bought, so the screen can say why
        # their margin will be empty rather than leaving it a mystery.
        # ponytail: one query per product, at a few dozen products. Fold it
        # into a grouped query in stock.levels() if the screen ever feels slow.
        no_price = {lv.product.id for lv in levels
                    if stock.last_cost_cents(s, lv.product.id) == 0}
        return request.app.state.templates.TemplateResponse(
            request, "stock.html",
            {"user": user, "tab": "more", "levels": levels,
             "no_price": no_price, "archived": archived,
             "reasons": [(r, S[f"stock_reason_{r}"])
                         for r in stock.MANUAL_REASONS],
             "error": _error(error)})


@router.post("/products")
def create(request: Request,
           name: str = Form(...), unit: str = Form(...),
           min_stock: str = Form("0"),
           sale_price_eur: str = Form(""),
           opening_qty: str = Form(""),
           opening_cost_eur: str = Form(""),
           user: User = Depends(security.require_user)):
    """The product and its opening movement are written in one session, so a
    mistyped opening price leaves neither behind. A product created with its
    opening quantity silently dropped is worse than a refused form: nothing on
    the screen would say the stock is wrong."""
    try:
        minimum = parse_qty(min_stock) if min_stock.strip() else 0.0
    except ValueError:
        return _back("stock_qty_invalid")
    if minimum < 0:
        # Checked here and not left to products.create: its ValueError would
        # fall into the name/unit branch below and show the wrong message.
        return _back("stock_qty_invalid")
    sale_cents = None
    if sale_price_eur.strip():
        try:
            sale_cents = treatments.parse_price(sale_price_eur)
        except ValueError:
            return _back("stock_cost_invalid")
    qty = cost = None
    if opening_qty.strip():
        try:
            qty = parse_qty(opening_qty)
        except ValueError:
            return _back("stock_qty_invalid")
        if abs(qty) < stock.QTY_EPSILON:
            return _back("stock_qty_zero")
        try:
            cost = (treatments.parse_price(opening_cost_eur)
                    if opening_cost_eur.strip() else 0)
        except ValueError:
            return _back("stock_cost_invalid")

    try:
        with request.app.state.db.session() as s:
            product = products.create(s, name, unit, created_by=str(user.id),
                                      min_stock=minimum,
                                      sale_price_cents=sale_cents)
            if qty is not None:
                stock.record(s, product.id, qty, "opening",
                             created_by=str(user.id), unit_cost_cents=cost)
    except ValueError as exc:
        key = ("product_unit_required" if "unit" in str(exc)
               else "product_name_required")
        return _back(key)
    return RedirectResponse("/stock", status_code=303)


@router.post("/{product_id}/movement")
def movement(request: Request, product_id: int,
             qty: str = Form(...), reason: str = Form(...),
             cost_eur: str = Form(""),
             user: User = Depends(security.require_user)):
    if reason not in stock.MANUAL_REASONS:
        return _back("stock_reason_invalid")
    try:
        amount = parse_qty(qty)
    except ValueError:
        return _back("stock_qty_invalid")
    if abs(amount) < stock.QTY_EPSILON:
        return _back("stock_qty_zero")
    # Waste takes stock off the shelf whichever way she types it. A correction
    # keeps its sign, because that is the only way to correct downwards.
    if reason == "waste":
        amount = -abs(amount)
    try:
        cost = treatments.parse_price(cost_eur) if cost_eur.strip() else None
    except ValueError:
        return _back("stock_cost_invalid")
    try:
        with request.app.state.db.session() as s:
            if cost is None:
                # An outbound movement with no price typed is charged at what
                # the stock cost, not at zero, or the waste is free.
                cost = stock.last_cost_cents(s, product_id)
            stock.record(s, product_id, amount, reason,
                         created_by=str(user.id), unit_cost_cents=cost)
    except (LookupError, ValueError):
        return RedirectResponse("/stock", status_code=303)
    return RedirectResponse("/stock", status_code=303)


@router.post("/{product_id}/archive")
def archive(request: Request, product_id: int,
            user: User = Depends(security.require_user)):
    _toggle(request, product_id, products.archive)
    return RedirectResponse("/stock", status_code=303)


@router.post("/{product_id}/unarchive")
def unarchive(request: Request, product_id: int,
              user: User = Depends(security.require_user)):
    _toggle(request, product_id, products.unarchive)
    return RedirectResponse("/stock?archived=true", status_code=303)


def _toggle(request: Request, product_id: int, action) -> None:
    """A missing id is a stale page, not a server fault: the list reloads
    without it rather than showing a stack trace."""
    try:
        with request.app.state.db.session() as s:
            action(s, product_id)
    except LookupError:
        pass


def _back(error: str) -> RedirectResponse:
    return RedirectResponse(f"/stock?error={error}", status_code=303)
```

- [ ] **Step 5: Write `app/templates/stock.html`**

No non-ASCII characters anywhere in this file; `tests/test_strings.py` fails
the build over a single one.

```html
{% extends "base.html" %}
{% block title %}{{ S["stock_title"] }}{% endblock %}
{% block heading %}{{ S["stock_title"] }}{% endblock %}
{% block body %}
{% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}

{% if not levels %}
<p class="muted">{{ S["stock_none"] }}</p>
{% endif %}

<ul class="list">
  {% for lv in levels %}
  <li class="card {% if lv.product.archived_at %}is-muted{% endif %}">
    <div class="row">
      <div class="row__main">
        <strong>{{ lv.product.name }}</strong>
        <div class="muted">
          {% if lv.product.archived_at %}
          <span class="pill">{{ S["archived"] }}</span>
          {% endif %}
          {% if lv.below_min %}<span class="pill pill--warn">{{ S["stock_low"] }}</span>{% endif %}
          {% if lv.product.id in no_price %}
          <span class="pill">{{ S["stock_no_price"] }}</span>
          {% endif %}
          <span class="num">{{ lv.qty | qty }}</span> {{ lv.product.unit }}
          {% if lv.product.min_stock %}
          &middot; min <span class="num">{{ lv.product.min_stock | qty }}</span>
          {% endif %}
        </div>
      </div>
      <form method="post"
            action="/stock/{{ lv.product.id }}/{{ 'unarchive' if lv.product.archived_at else 'archive' }}">
        <button class="secondary" type="submit">
          {{ S["unarchive"] if lv.product.archived_at else S["archive"] }}
        </button>
      </form>
    </div>

    {% if not lv.product.archived_at %}
    <details>
      <summary>{{ S["stock_movement"] }}</summary>
      <form method="post" action="/stock/{{ lv.product.id }}/movement">
        <label for="qty_{{ lv.product.id }}">{{ S["stock_qty"] }}</label>
        <input id="qty_{{ lv.product.id }}" name="qty" inputmode="decimal" required>
        <label for="reason_{{ lv.product.id }}">{{ S["stock_reason"] }}</label>
        <select id="reason_{{ lv.product.id }}" name="reason" required>
          {% for value, label in reasons %}
          <option value="{{ value }}">{{ label }}</option>
          {% endfor %}
        </select>
        <label for="cost_{{ lv.product.id }}">{{ S["opening_cost"] }}</label>
        <input id="cost_{{ lv.product.id }}" name="cost_eur" inputmode="decimal">
        <button type="submit">{{ S["save"] }}</button>
      </form>
    </details>
    {% endif %}
  </li>
  {% endfor %}
</ul>

<p class="stack-top">
  <a href="/stock{% if not archived %}?archived=true{% endif %}">
    {{ S["show_archived_products"] }}</a>
</p>

<details class="card stack-top">
  <summary>{{ S["stock_new"] }}</summary>
  <form method="post" action="/stock/products">
    <label for="name">{{ S["product_name"] }}</label>
    <input id="name" name="name" required>
    <label for="unit">{{ S["product_unit"] }}</label>
    <input id="unit" name="unit" placeholder="{{ S['product_unit_hint'] }}" required>
    <label for="min_stock">{{ S["product_min_stock"] }}</label>
    <input id="min_stock" name="min_stock" inputmode="decimal" value="0">
    <label for="sale_price_eur">{{ S["product_sale_price"] }}</label>
    <input id="sale_price_eur" name="sale_price_eur" inputmode="decimal">
    <label for="opening_qty">{{ S["opening_qty"] }}</label>
    <input id="opening_qty" name="opening_qty" inputmode="decimal">
    <label for="opening_cost_eur">{{ S["opening_cost"] }}</label>
    <input id="opening_cost_eur" name="opening_cost_eur" inputmode="decimal">
    <button type="submit">{{ S["save"] }}</button>
  </form>
</details>
{% endblock %}
```

- [ ] **Step 6: Add the `qty` template filter**

A raw float renders as `3.3333333333333335`. In `app/display.py`:

```python
def qty(value: float | None) -> str:
    """A stock quantity, at most two decimals, comma as the separator.

    Trailing zeros come off, so three whole bottles read "3" and not "3,00",
    while a part used one reads "3,4". Rounded for display only: the stored
    value keeps its full precision, because rounding every consumption to two
    places would drift the shelf figure by a bottle a year.
    """
    text = f"{round(float(value or 0.0), 2):.2f}".rstrip("0").rstrip(".")
    return (text or "0").replace(".", ",")
```

In `app/main.py`, next to the `eur` filter:

```python
    templates.env.filters["qty"] = display.qty
```

Add its test to `tests/test_money.py`:

```python
def test_qty_drops_trailing_zeros_and_uses_a_comma():
    from app.display import qty
    assert qty(3) == "3"
    assert qty(3.4) == "3,4"
    assert qty(1 / 3) == "0,33"
    assert qty(None) == "0"
    assert qty(-1.5) == "-1,5"
    assert qty(0.001) == "0"
```

- [ ] **Step 7: Wire the router and the menu**

In `app/main.py`, extend the existing router import line with `stock`:

```python
from app.routers import api, auth, calendar, clients, stock, today, visits
```

and, after `app.include_router(settings_router.router)`:

```python
app.include_router(stock.router)
```

`expenses` is added to both lines in Task 7, not here: importing a module that
does not exist yet fails at startup and every test in the suite goes red.

In `app/templates/settings_index.html`, add a list item before the treatments
link:

```html
  <li class="card"><a href="/stock">{{ S["settings_stock"] }}</a></li>
```

- [ ] **Step 8: Run the tests to verify they pass**

Run:

    docker build -t pedikur-dev . && \
    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests -q

Expected: PASS, 289 tests (279 + 9 route tests + 1 filter test).

- [ ] **Step 9: Screenshot loop**

Run the dev container and the headless Chrome recipe from phase 1 Task 3 Step 5
against `/stock` at 390px wide. Check three things in the image, not in the
markup: the "Kevés" pill is readable against the card, the movement `<details>`
does not push the archive button off the row, and the new-product form's submit
button has a gap above it (the `details.card > form > button[type="submit"]`
rule from commit 6cc27fe covers it; confirm it applies here too).

- [ ] **Step 10: Commit**

```bash
git add app/routers/stock.py app/templates/stock.html app/main.py \
        app/display.py app/templates/settings_index.html app/strings/hu.py \
        tests/test_stock_routes.py tests/test_money.py app/static/app.css
git commit -m "feat(pedikur): the stock screen, with the quantity computed from the ledger"
```

---

### Task 4: Treatment Recipes

**Files:**
- Create: `app/services/recipes.py`
- Create: `app/templates/settings_recipe.html`
- Modify: `app/routers/settings.py`
- Modify: `app/templates/settings_treatments.html`
- Modify: `app/strings/hu.py`
- Test: `tests/test_recipes.py`

**Interfaces:**
- Consumes: `models.TreatmentRecipe`, `products.list_all`, `treatments.list_all`.
- Produces:
  - `recipes.for_treatment(session, treatment_id) -> list[TreatmentRecipe]`
  - `recipes.set_for(session, treatment_id, product_id, treatments_per_unit) -> TreatmentRecipe`
  - `recipes.remove(session, recipe_id) -> None`
  - `recipes.by_treatment(session) -> dict[int, list[TreatmentRecipe]]`
  - the routes `GET /settings/treatments/{treatment_id}/recipe`,
    `POST /settings/treatments/{treatment_id}/recipe`,
    `POST /settings/recipes/{recipe_id}/remove`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_recipes.py
import pytest

from app import migrate
from app.db import Database
from app.services import products, recipes, treatments


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


@pytest.fixture
def ids(db):
    with db.session() as s:
        t = treatments.create(s, "Pedikur", 45, 2500, created_by="1")
        p = products.create(s, "Lakk", "flakon", created_by="1")
        return t.id, p.id


def test_a_recipe_is_stored_and_read_back(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        recipes.set_for(s, treatment_id, product_id, 30)
    with db.session() as s:
        rows = recipes.for_treatment(s, treatment_id)
        assert len(rows) == 1
        assert rows[0].treatments_per_unit == 30
        assert rows[0].product.name == "Lakk"


def test_setting_the_same_pair_twice_updates_rather_than_duplicates(db, ids):
    """Two rows for one pair would double that treatment's consumption, and
    nothing downstream would say why the lacquer runs out twice as fast."""
    treatment_id, product_id = ids
    with db.session() as s:
        recipes.set_for(s, treatment_id, product_id, 30)
        recipes.set_for(s, treatment_id, product_id, 20)
    with db.session() as s:
        rows = recipes.for_treatment(s, treatment_id)
        assert len(rows) == 1
        assert rows[0].treatments_per_unit == 20


def test_a_yield_of_zero_is_refused(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        with pytest.raises(ValueError):
            recipes.set_for(s, treatment_id, product_id, 0)


def test_a_negative_yield_is_refused(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        with pytest.raises(ValueError):
            recipes.set_for(s, treatment_id, product_id, -5)


def test_removing_a_recipe_leaves_the_treatment_alone(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        row = recipes.set_for(s, treatment_id, product_id, 30)
        recipes.remove(s, row.id)
    with db.session() as s:
        assert recipes.for_treatment(s, treatment_id) == []
        assert len(treatments.list_all(s)) == 1


def test_by_treatment_groups_every_recipe_in_one_query(db, ids):
    treatment_id, product_id = ids
    with db.session() as s:
        other = products.create(s, "Gel", "flakon", created_by="1")
        recipes.set_for(s, treatment_id, product_id, 30)
        recipes.set_for(s, treatment_id, other.id, 10)
    with db.session() as s:
        grouped = recipes.by_treatment(s)
        assert sorted(r.product.name for r in grouped[treatment_id]) == ["Gel", "Lakk"]


def test_a_treatment_with_no_recipe_is_absent_rather_than_empty(db, ids):
    """Callers use `.get(id, [])`. An empty list stored for every treatment
    would hide the difference between "no recipe yet" and "a recipe of
    nothing", and only the first one is normal."""
    treatment_id, _ = ids
    with db.session() as s:
        assert treatment_id not in recipes.by_treatment(s)
```

- [ ] **Step 2: Run it to verify it fails**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests/test_recipes.py -q

Expected: FAIL, `ImportError: cannot import name 'recipes'`

- [ ] **Step 3: Write `app/services/recipes.py`**

```python
"""How many Treatments one unit of a Product lasts for.

The question is asked this way round on purpose: nobody knows they use 0.4 ml
of lacquer, and everybody knows a bottle gives about thirty fills. Consumption
is then 1/treatments_per_unit, which is where the fractional stock figure
comes from.

Recipes are configuration, not history, so remove() is a real delete. Nothing
is lost by it: consumption is already posted as Stock Movements, and those are
append-only and untouched by anything in this module.

Only the expensive materials get a recipe (lacquer, gel, abrasive caps), by
decision on 2026-09-12. A Treatment with no recipe posts no consumption, and
that is not a bug. The consequence travels to the dashboard: the margin figure
counts only what carries a recipe, and must never be labelled as though it
covered everything.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TreatmentRecipe


def for_treatment(session: Session, treatment_id: int) -> list[TreatmentRecipe]:
    return list(session.scalars(
        select(TreatmentRecipe)
        .where(TreatmentRecipe.treatment_id == treatment_id)
        .order_by(TreatmentRecipe.id)))


def by_treatment(session: Session) -> dict[int, list[TreatmentRecipe]]:
    """Every recipe, grouped, in one query. The treatment list screen needs
    all of them at once and the reconcile needs one treatment's worth; this is
    the shape that keeps the list screen off an N+1."""
    grouped: dict[int, list[TreatmentRecipe]] = defaultdict(list)
    for row in session.scalars(
            select(TreatmentRecipe).order_by(TreatmentRecipe.id)):
        grouped[row.treatment_id].append(row)
    return dict(grouped)


def set_for(session: Session, treatment_id: int, product_id: int,
            treatments_per_unit: float) -> TreatmentRecipe:
    """Upsert on the (treatment, product) pair.

    Upsert rather than insert because the UNIQUE index would otherwise raise
    an IntegrityError at commit, long after the route left its try block, and
    correcting a yield she guessed badly is the normal case rather than the
    exceptional one.
    """
    yield_per_unit = float(treatments_per_unit)
    if yield_per_unit <= 0:
        # Also a CHECK constraint. Repeated here because consumption is
        # 1/this: a zero reaching the close path is a ZeroDivisionError with a
        # client in the chair.
        raise ValueError("one unit has to last for at least a fraction of a treatment")
    row = session.scalars(
        select(TreatmentRecipe)
        .where(TreatmentRecipe.treatment_id == treatment_id,
               TreatmentRecipe.product_id == product_id)).one_or_none()
    if row is None:
        row = TreatmentRecipe(treatment_id=treatment_id, product_id=product_id,
                              treatments_per_unit=yield_per_unit)
        session.add(row)
    else:
        row.treatments_per_unit = yield_per_unit
    session.flush()
    return row


def remove(session: Session, recipe_id: int) -> None:
    row = session.get(TreatmentRecipe, recipe_id)
    if row is None:
        raise LookupError(f"no recipe {recipe_id}")
    session.delete(row)
    session.flush()
```

- [ ] **Step 4: Add the strings**

```python
    "recipe_title": "Recept",
    "recipe": "Recept",
    "recipe_none": "Nincs hozzá anyag",
    "recipe_product": "Anyag",
    "recipe_yield": "Hány kezelésre elég egy egység",
    "recipe_yield_hint": "egy flakon kb. 30 töltés",
    "recipe_yield_invalid": "A szám nem jó: egy egységnek legalább egy töredék kezelésre elegendőnek kell lennie.",
    "recipe_no_products": "Előbb vegyél fel terméket a Készlet alatt.",
    "recipe_partial_hint": "Csak a drága anyagokhoz kell. Ami nincs itt, arra nem számol fedezetet.",
```

- [ ] **Step 5: Add the routes to `app/routers/settings.py`**

Extend the `_ERRORS` frozenset with `"recipe_yield_invalid"`, add
`from app.services import products, recipes` to the imports, and append:

```python
@router.get("/treatments/{treatment_id}/recipe")
def recipe_form(request: Request, treatment_id: int, error: str | None = None,
                user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        treatment = s.get(Treatment, treatment_id)
        if treatment is None:
            return RedirectResponse("/settings/treatments", status_code=303)
        return _render(request, "settings_recipe.html",
                       {"user": user, "tab": "more", "treatment": treatment,
                        "rows": recipes.for_treatment(s, treatment_id),
                        "products": products.list_all(s),
                        "error": _error(error)})


@router.post("/treatments/{treatment_id}/recipe")
def recipe_save(request: Request, treatment_id: int,
                product_id: int = Form(...),
                treatments_per_unit: str = Form(...),
                user: User = Depends(security.require_user)):
    try:
        with request.app.state.db.session() as s:
            recipes.set_for(s, treatment_id, product_id,
                            float(treatments_per_unit.replace(",", ".")))
    except (ValueError, TypeError):
        return RedirectResponse(
            f"/settings/treatments/{treatment_id}/recipe"
            f"?error=recipe_yield_invalid", status_code=303)
    return RedirectResponse(f"/settings/treatments/{treatment_id}/recipe",
                            status_code=303)


@router.post("/recipes/{recipe_id}/remove")
def recipe_remove(request: Request, recipe_id: int, treatment_id: int = Form(...),
                  user: User = Depends(security.require_user)):
    try:
        with request.app.state.db.session() as s:
            recipes.remove(s, recipe_id)
    except LookupError:
        pass
    return RedirectResponse(f"/settings/treatments/{treatment_id}/recipe",
                            status_code=303)
```

`Treatment` needs adding to the `from app.models import ...` line in that file.

- [ ] **Step 6: Write `app/templates/settings_recipe.html`**

```html
{% extends "base.html" %}
{% block title %}{{ S["recipe_title"] }}{% endblock %}
{% block heading %}{{ treatment.name }}{% endblock %}
{% block body %}
{% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}
<p class="muted">{{ S["recipe_partial_hint"] }}</p>

{% if not rows %}
<p class="muted">{{ S["recipe_none"] }}</p>
{% endif %}

<ul class="list">
  {% for r in rows %}
  <li class="card row">
    <div class="row__main">
      <strong>{{ r.product.name }}</strong>
      <div class="muted">
        <span class="num">{{ r.treatments_per_unit | qty }}</span>
        / 1 {{ r.product.unit }}
      </div>
    </div>
    <form method="post" action="/settings/recipes/{{ r.id }}/remove">
      <input type="hidden" name="treatment_id" value="{{ treatment.id }}">
      <button class="secondary" type="submit">{{ S["remove"] }}</button>
    </form>
  </li>
  {% endfor %}
</ul>

{% if products %}
<form method="post" action="/settings/treatments/{{ treatment.id }}/recipe"
      class="card stack-top">
  <label for="product_id">{{ S["recipe_product"] }}</label>
  <select id="product_id" name="product_id" required>
    {% for p in products %}
    <option value="{{ p.id }}">{{ p.name }} ({{ p.unit }})</option>
    {% endfor %}
  </select>
  <label for="treatments_per_unit">{{ S["recipe_yield"] }}</label>
  <input id="treatments_per_unit" name="treatments_per_unit" inputmode="decimal"
         placeholder="{{ S['recipe_yield_hint'] }}" required>
  <button type="submit">{{ S["save"] }}</button>
</form>
{% else %}
<p class="muted stack-top">{{ S["recipe_no_products"] }}</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 7: Link it from the treatment list**

In `app/templates/settings_treatments.html`, inside the `row__main` div, after
the duration and price line:

```html
      <div><a href="/settings/treatments/{{ t.id }}/recipe">{{ S["recipe"] }}</a></div>
```

- [ ] **Step 8: Run the tests to verify they pass**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests -q

Expected: PASS, 296 tests (289 + 7).

- [ ] **Step 9: Screenshot loop**

`/settings/treatments` and `/settings/treatments/1/recipe` at 390px. The one
thing to check in the image: the recipe link under a treatment does not collide
with the "Kivezetés" button on the same row.

- [ ] **Step 10: Commit**

```bash
git add app/services/recipes.py app/templates/settings_recipe.html \
        app/routers/settings.py app/templates/settings_treatments.html \
        app/strings/hu.py tests/test_recipes.py app/static/app.css
git commit -m "feat(pedikur): treatment recipes, asked as a yield rather than a dose"
```

---

### Task 5: Consumption, posted by reconciling

This is the task that needed a decision rather than a keyboard. The argument is
written out because whoever maintains this next will be tempted to simplify it
back.

**The rejected approach** was to post consumption on the first close, guarded by
`closed_at`, the same way `close()` already freezes prices. It has a hole: a
mis-tapped Done, then the forgotten treatment added, then Done again. The price
is right in that case, because an override is applied on any close. The stock is
not, because the second treatment's consumption never posts. Nobody counts
bottles against the database, so the error is permanent and silent.

**The approach taken** computes, at every close, how much consumption *should*
exist for this visit, compares it with how much is *already* posted for this
visit, and writes the difference. It is idempotent by arithmetic rather than by
a flag: closing twice computes a difference of zero and writes nothing. It
self-heals when a treatment is added or removed after the fact. It preserves the
append-only rule, because a correction is a new row rather than an edit. And it
needs no reference to `closed_at` at all, so there is one fewer invariant to
keep in step.

It also makes `set_status` correct for free. Desired consumption is defined as
zero unless the Visit is `done`, so cancelling a closed Visit returns everything
it consumed, through the same function, with no second code path.

**Files:**
- Modify: `app/services/stock.py` (add `reconcile_visit`)
- Modify: `app/services/visits.py` (`close` and `set_status` call it)
- Modify: `app/routers/visits.py`, `app/routers/today.py` (pass `created_by`)
- Test: `tests/test_visits.py`

**Interfaces:**
- Consumes: `recipes.for_treatment`, `stock.record`, `stock.last_cost_cents`.
- Produces: `stock.reconcile_visit(session, visit, created_by) -> list[StockMovement]`.
  `visits.close` and `visits.set_status` both gain a `created_by: str = "api"`
  keyword argument.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_visits.py - append
import pytest

from app.services import products, recipes, stock, visits


@pytest.fixture
def recipe_setup(db):
    """One treatment that uses a third of a bottle, one that uses nothing."""
    with db.session() as s:
        lakk = products.create(s, "Lakk", "flakon", created_by="1")
        stock.record(s, lakk.id, 5, "purchase", created_by="1",
                     unit_cost_cents=1200)
        pedikur = treatments.create(s, "Pedikur", 45, 2500, created_by="1")
        masszazs = treatments.create(s, "Masszazs", 30, 1500, created_by="1")
        recipes.set_for(s, pedikur.id, lakk.id, 3)
        client = clients.create(s, "Teszt Kliens", created_by="1")
        return {"lakk": lakk.id, "pedikur": pedikur.id,
                "masszazs": masszazs.id, "client": client.id}


def _book(db, setup, treatment_ids, hour=10):
    with db.session() as s:
        visit = visits.book(s, setup["client"],
                            datetime(2026, 9, 14, hour, 0, tzinfo=TZ),
                            treatment_ids, created_by="1")
        return visit.id


def test_closing_posts_the_consumption_from_the_recipe(db, recipe_setup):
    visit_id = _book(db, recipe_setup, [recipe_setup["pedikur"]])
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        # 5 bought, one third of a bottle used
        assert stock.quantity(s, recipe_setup["lakk"]) == pytest.approx(5 - 1 / 3)


def test_the_consumption_is_charged_at_the_last_purchase_price(db, recipe_setup):
    visit_id = _book(db, recipe_setup, [recipe_setup["pedikur"]])
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        row = s.scalars(select(StockMovement)
                        .where(StockMovement.reason == "consumption")).one()
        assert row.unit_cost_cents == 1200
        assert row.visit_id == visit_id


def test_a_treatment_with_no_recipe_posts_nothing(db, recipe_setup):
    visit_id = _book(db, recipe_setup, [recipe_setup["masszazs"]])
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, recipe_setup["lakk"]) == 5.0


def test_closing_twice_posts_the_consumption_once(db, recipe_setup):
    """The reason the reconcile exists. A double tap on a phone, or a retried
    request, must not take two thirds of a bottle off the shelf."""
    visit_id = _book(db, recipe_setup, [recipe_setup["pedikur"]])
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, recipe_setup["lakk"]) == pytest.approx(5 - 1 / 3)
        rows = list(s.scalars(select(StockMovement)
                              .where(StockMovement.reason == "consumption")))
        assert len(rows) == 1


def test_a_treatment_added_after_the_close_still_posts_its_consumption(db, recipe_setup):
    """The hole the rejected first-close guard would have left: the price of
    the added treatment would be right and its stock would not."""
    visit_id = _book(db, recipe_setup, [recipe_setup["masszazs"]])
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
        visits.add_treatment(s, visit_id, recipe_setup["pedikur"])
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, recipe_setup["lakk"]) == pytest.approx(5 - 1 / 3)


def test_a_treatment_removed_after_the_close_gives_the_stock_back(db, recipe_setup):
    visit_id = _book(db, recipe_setup,
                     [recipe_setup["pedikur"], recipe_setup["masszazs"]])
    with db.session() as s:
        visit = visits.close(s, visit_id, created_by="1")
        item = next(i for i in visit.items
                    if i.treatment_id == recipe_setup["pedikur"])
        visits.remove_item(s, visit_id, item.id)
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, recipe_setup["lakk"]) == pytest.approx(5.0)


def test_cancelling_a_closed_visit_returns_everything_it_consumed(db, recipe_setup):
    """Work that did not happen consumed nothing. Falls out of the reconcile
    for free: a Visit that is not done has a desired consumption of zero."""
    visit_id = _book(db, recipe_setup, [recipe_setup["pedikur"]])
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        visits.set_status(s, visit_id, "cancelled", created_by="1")
    with db.session() as s:
        assert stock.quantity(s, recipe_setup["lakk"]) == pytest.approx(5.0)


def test_reclosing_after_a_cancellation_posts_it_again(db, recipe_setup):
    visit_id = _book(db, recipe_setup, [recipe_setup["pedikur"]])
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        visits.set_status(s, visit_id, "cancelled", created_by="1")
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, recipe_setup["lakk"]) == pytest.approx(5 - 1 / 3)


def test_consumption_is_posted_even_with_nothing_on_the_shelf(db, recipe_setup):
    """Refusing here would mean a "nincs eleg lakk" error in the middle of a
    close, with the client in the chair. The ledger records the truth and the
    stock screen shows it as negative."""
    with db.session() as s:
        stock.record(s, recipe_setup["lakk"], -5, "correction", created_by="1")
    visit_id = _book(db, recipe_setup, [recipe_setup["pedikur"]])
    with db.session() as s:
        visits.close(s, visit_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, recipe_setup["lakk"]) == pytest.approx(-1 / 3)
```

The fixtures, imports and `TZ` constant follow whatever `tests/test_visits.py`
already uses; read the top of that file and match it rather than adding a second
set.

- [ ] **Step 2: Run them to verify they fail**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests/test_visits.py -q

Expected: FAIL. `close()` takes no `created_by`, `visits.remove_item` does not
exist, and no consumption is posted.

- [ ] **Step 3: Add `reconcile_visit` to `app/services/stock.py`**

Append to the module, and add `from app.models import Visit` and
`from app.services import recipes` to its imports:

```python
# The two reasons a Visit owns. Everything else on a product's ledger belongs
# to a purchase, an opening balance or a correction, and the reconcile must
# never touch those: they are not its to compute.
VISIT_REASONS = ("consumption", "sale")


def reconcile_visit(session: Session, visit: Visit,
                    created_by: str) -> list[StockMovement]:
    """Make this Visit's stock ledger agree with what the Visit now says.

    Computes what should have gone off the shelf for this Visit, subtracts
    what already has, and appends the difference. Nothing is edited and
    nothing is deleted, so the append-only rule holds.

    Three properties come out of doing it this way rather than posting once on
    the first close:

    - Idempotent by arithmetic. Closing twice computes a difference of zero
      and writes no row, without consulting closed_at or any other flag.
    - Self-healing. A Treatment added or removed after the close moves the
      difference, and the next close writes exactly the correction.
    - Symmetric. A Visit that is not done consumed nothing, so cancelling a
      closed Visit returns its stock through this same function with no second
      code path.
    """
    desired: dict[tuple[int, str], float] = {}
    # Only a done Visit consumes anything. Work that was cancelled or not
    # shown up for used no lacquer, and this one line is what makes
    # set_status correct without a second implementation.
    if visit.status == "done":
        for item in visit.items:
            if item.kind == "treatment" and item.treatment_id is not None:
                for row in recipes.for_treatment(session, item.treatment_id):
                    key = (row.product_id, "consumption")
                    desired[key] = (desired.get(key, 0.0)
                                    + item.qty / row.treatments_per_unit)
            elif item.kind == "product" and item.product_id is not None:
                key = (item.product_id, "sale")
                desired[key] = desired.get(key, 0.0) + item.qty

    # Stored negative because stock left the shelf; flipped here so both sides
    # of the comparison mean "how much went out".
    posted: dict[tuple[int, str], float] = {
        (product_id, reason): -float(total)
        for product_id, reason, total in session.execute(
            select(StockMovement.product_id, StockMovement.reason,
                   func.sum(StockMovement.qty))
            .where(StockMovement.visit_id == visit.id,
                   StockMovement.reason.in_(VISIT_REASONS))
            .group_by(StockMovement.product_id, StockMovement.reason))}

    written: list[StockMovement] = []
    for key in sorted(set(desired) | set(posted)):
        product_id, reason = key
        delta = desired.get(key, 0.0) - posted.get(key, 0.0)
        # Compared against an epsilon, not against zero: one third of a bottle
        # summed by SQLite over two rows and the same third summed by Python
        # can differ in the last bit, and that difference must not become a
        # movement of 1e-17 on every single close.
        if abs(delta) < QTY_EPSILON:
            continue
        written.append(record(
            session, product_id=product_id, qty=-delta, reason=reason,
            created_by=created_by, visit_id=visit.id,
            unit_cost_cents=last_cost_cents(session, product_id)))
    return written
```

- [ ] **Step 4: Call it from `app/services/visits.py`**

Add `from app.services import stock` to the imports. Rename
`remove_treatment` to `remove_item` and make its guard conditional, since a
product line has no minimum:

```python
def remove_item(session: Session, visit_id: int, item_id: int) -> Visit:
    """Undo a mis-ticked line, Treatment or Product.

    ends_at is left where it is: it only ever grows, and shrinking it could
    hand a slot to someone while the client is still in the chair.

    The "at least one Treatment" guard applies to Treatments only. A Visit
    with no Product on it is the normal case.
    """
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    item = next((i for i in visit.items if i.id == item_id), None)
    if item is None:
        raise LookupError(f"no item {item_id} on visit {visit_id}")
    if (item.kind == "treatment"
            and len([i for i in visit.items if i.kind == "treatment"]) <= 1):
        raise ValueError("a Visit needs at least one Treatment")
    visit.items.remove(item)
    session.delete(item)
    session.flush()
    return visit
```

In `close()`, add the parameter and the call. The signature becomes:

```python
def close(session: Session, visit_id: int,
          price_overrides: dict[int, int] | None = None,
          findings: str | None = None, note: str | None = None,
          created_by: str = "api") -> Visit:
```

and the last three lines before `return visit` become:

```python
    visit.status = "done"
    if first_close:
        visit.closed_at = timeutil.to_utc_iso(timeutil.local_now())
    session.flush()
    # After the status is set, never before: the reconcile reads visit.status
    # to decide whether this Visit consumed anything at all.
    stock.reconcile_visit(session, visit, created_by)
    session.flush()
    return visit
```

In `set_status()`, the same:

```python
def set_status(session: Session, visit_id: int, status: str,
               created_by: str = "api") -> Visit:
    if status not in STATUSES:
        raise ValueError(f"bad status: {status}")
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    _claim_slot_again(session, visit, status)
    visit.status = status
    session.flush()
    # Cancelling a closed Visit gives back what it consumed. Same function,
    # because a Visit that is not done has a desired consumption of zero.
    stock.reconcile_visit(session, visit, created_by)
    session.flush()
    return visit
```

The default of `"api"` matches the `created_by` convention in the spec and keeps
the existing `/api/*` callers working unchanged.

There is no import cycle: `visits` imports `stock`, and `stock` imports
`models`, `products`, `recipes` and `timeutil`, none of which import `visits`.

- [ ] **Step 5: Pass the real user from the routers**

In `app/routers/visits.py`, in the `close` route:

```python
            visits.close(s, visit_id, price_overrides=overrides,
                         findings=None if findings is None else str(findings),
                         note=None if note is None else str(note),
                         created_by=str(user.id))
```

in the `status` route:

```python
            visits.set_status(s, visit_id, value, created_by=str(user.id))
```

and rename the remove route, since the item may now be a Product:

```python
@router.post("/{visit_id}/items/{item_id}/remove")
def remove_item(request: Request, visit_id: int, item_id: int,
                user: User = Depends(security.require_user)):
```

with `visits.remove_item(s, visit_id, item_id)` in its body. Update the
`action` in `app/templates/visit_close.html` to
`/visits/{{ visit.id }}/items/{{ item.id }}/remove`, and update the two route
tests in `tests/test_visits_routes.py` that post to the old path.

In `app/routers/today.py`, the walk-in close:

```python
            visits.close(s, visit.id, created_by=str(user.id))
```

- [ ] **Step 6: Run the whole suite**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests -q

Expected: PASS, 305 tests (296 + 9). If any phase 1 test fails, it is the
`remove_treatment` rename; fix the call site, not the test's intent.

- [ ] **Step 7: Commit**

```bash
git add app/services/stock.py app/services/visits.py app/routers/visits.py \
        app/routers/today.py app/templates/visit_close.html \
        tests/test_visits.py tests/test_visits_routes.py
git commit -m "feat(pedikur): closing a visit posts its consumption, by reconciling rather than by a flag"
```

- [ ] **Step 8: STOP.** Report to the human: a screenshot of the close screen,
and the movements a test close produced. Wait for a yes before Task 6.

---

### Task 6: Selling a product at the close

**Files:**
- Modify: `app/services/visits.py` (`add_product`, `total_cents`)
- Modify: `app/routers/visits.py`
- Modify: `app/routers/api.py` (use `visits.total_cents`)
- Modify: `app/templates/visit_close.html`
- Modify: `app/strings/hu.py`
- Test: `tests/test_visits_routes.py`

**Interfaces:**
- Consumes: `products.for_sale`, `products.get`.
- Produces: `visits.add_product(session, visit_id, product_id, qty=1.0) -> Visit`,
  `visits.total_cents(visit) -> int`, the route
  `POST /visits/{visit_id}/products`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visits_routes.py - append
from app.services import products, stock


def test_a_product_can_be_sold_at_the_close(logged_in, a_visit):
    with logged_in.app.state.db.session() as s:
        krem = products.create(s, "Krem", "tubus", created_by="1",
                               sale_price_cents=850)
        stock.record(s, krem.id, 4, "purchase", created_by="1",
                     unit_cost_cents=500)
        krem_id = krem.id
    logged_in.post(f"/visits/{a_visit}/products",
                   data={"product_id": krem_id, "qty": "1"})
    logged_in.post(f"/visits/{a_visit}/close", data={})
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, krem_id) == 3.0


def test_the_sale_price_is_frozen_on_the_line(logged_in, a_visit):
    """Same rule as a Treatment, and frozen earlier: the price is snapshotted
    when the product is added, not at the close, because close() skips every
    item whose kind is not treatment. Raising the shelf price next month must
    not rewrite what this client paid today."""
    with logged_in.app.state.db.session() as s:
        krem = products.create(s, "Krem", "tubus", created_by="1",
                               sale_price_cents=850)
        krem_id = krem.id
    logged_in.post(f"/visits/{a_visit}/products",
                   data={"product_id": krem_id, "qty": "2"})
    logged_in.post(f"/visits/{a_visit}/close", data={})
    with logged_in.app.state.db.session() as s:
        products.update(s, krem_id, sale_price_cents=1200)
    with logged_in.app.state.db.session() as s:
        item = next(i for i in s.get(Visit, a_visit).items
                    if i.kind == "product")
        assert item.unit_price_cents == 850
        assert item.qty == 2.0


def test_a_product_with_no_sale_price_cannot_be_sold(logged_in, a_visit):
    with logged_in.app.state.db.session() as s:
        lakk = products.create(s, "Lakk", "flakon", created_by="1")
        lakk_id = lakk.id
    r = logged_in.post(f"/visits/{a_visit}/products",
                       data={"product_id": lakk_id, "qty": "1"})
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert [i for i in s.get(Visit, a_visit).items
                if i.kind == "product"] == []


def test_a_sold_product_can_be_taken_off_again(logged_in, a_visit):
    with logged_in.app.state.db.session() as s:
        krem = products.create(s, "Krem", "tubus", created_by="1",
                               sale_price_cents=850)
        stock.record(s, krem.id, 4, "purchase", created_by="1",
                     unit_cost_cents=500)
        krem_id = krem.id
    logged_in.post(f"/visits/{a_visit}/products",
                   data={"product_id": krem_id, "qty": "1"})
    logged_in.post(f"/visits/{a_visit}/close", data={})
    with logged_in.app.state.db.session() as s:
        item = next(i for i in s.get(Visit, a_visit).items
                    if i.kind == "product")
        item_id = item.id
    logged_in.post(f"/visits/{a_visit}/items/{item_id}/remove")
    logged_in.post(f"/visits/{a_visit}/close", data={})
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, krem_id) == 4.0


def test_the_total_covers_treatments_and_products(logged_in, a_visit):
    with logged_in.app.state.db.session() as s:
        krem = products.create(s, "Krem", "tubus", created_by="1",
                               sale_price_cents=850)
        krem_id = krem.id
    logged_in.post(f"/visits/{a_visit}/products",
                   data={"product_id": krem_id, "qty": "2"})
    logged_in.post(f"/visits/{a_visit}/close", data={})
    with logged_in.app.state.db.session() as s:
        visit = s.get(Visit, a_visit)
        treatment_total = sum(i.unit_price_cents for i in visit.items
                              if i.kind == "treatment")
        assert visits.total_cents(visit) == treatment_total + 1700
```

`a_visit` is a fixture returning the id of a booked visit; if
`tests/test_visits_routes.py` has no such fixture, add one that books through
the service the way the existing tests in that file do.

- [ ] **Step 2: Run it to verify it fails**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests/test_visits_routes.py -q

Expected: FAIL, 404 on `/visits/{id}/products`.

- [ ] **Step 3: Add `add_product` and `total_cents` to `app/services/visits.py`**

```python
def add_product(session: Session, visit_id: int, product_id: int,
                qty: float = 1.0) -> Visit:
    """Sell a Product on this Visit.

    The price is snapshotted onto the Visit Item exactly the way a Treatment's
    is: raising the shelf price next month must not rewrite what this client
    paid today.

    ends_at is untouched. Handing over a tube of cream does not lengthen the
    appointment, and growing the window here would push into the next client's
    slot for nothing.
    """
    visit = session.get(Visit, visit_id)
    if visit is None:
        raise LookupError(f"no visit {visit_id}")
    product = products.get(session, product_id)
    if product.archived_at is not None:
        raise ValueError(f"product {product_id} is archived")
    if product.sale_price_cents is None:
        # Not for sale is not the same as free. Without this, a consumable
        # would land on the bill at zero and the client would be charged
        # nothing for it, quietly.
        raise ValueError(f"product {product_id} has no sale price")
    amount = float(qty)
    if amount <= 0:
        raise ValueError("a sold quantity has to be positive")
    visit.items.append(VisitItem(kind="product", product_id=product.id,
                                 qty=amount,
                                 unit_price_cents=product.sale_price_cents))
    session.flush()
    return visit


def total_cents(visit: Visit) -> int:
    """What the client owes: every line, quantity included.

    Rounded per line, so two half-price halves cannot sum to a fraction of a
    cent and turn the column's integer CHECK into a 500.
    """
    return sum(round(item.unit_price_cents * item.qty) for item in visit.items)
```

Add `from app.services import products` to the imports.

In `app/routers/api.py`, delete the local `_total_cents` and call
`visits.total_cents` instead; there is exactly one call site.

- [ ] **Step 4: Add the route**

In `app/routers/visits.py`, extend `_ERRORS` with `"visit_product_invalid"` and
add:

```python
@router.post("/{visit_id}/products")
def add_product(request: Request, visit_id: int,
                product_id: int = Form(...), qty: str = Form("1"),
                user: User = Depends(security.require_user)):
    try:
        amount = stock_routes.parse_qty(qty)
    except ValueError:
        return RedirectResponse(
            f"/visits/{visit_id}/close?error=visit_product_invalid",
            status_code=303)
    try:
        with request.app.state.db.session() as s:
            visits.add_product(s, visit_id, product_id, amount)
    except ValueError:
        return RedirectResponse(
            f"/visits/{visit_id}/close?error=visit_product_invalid",
            status_code=303)
    except LookupError:
        return RedirectResponse("/?error=visit_gone", status_code=303)
    return RedirectResponse(f"/visits/{visit_id}/close", status_code=303)
```

with `from app.routers import stock as stock_routes` at the top. `parse_qty`
lives in the stock router because that is where the stock screen needed it
first; importing it is smaller than a third copy of a decimal parser.

In the `close_form` route, the context needs the sellable products:

```python
            {"user": user, "tab": "today", "visit": visit,
             "treatments": treatments.list_active(s),
             "sellable": products.for_sale(s),
             "total_cents": visits.total_cents(visit),
             "error": S[error] if error in _ERRORS else None})
```

- [ ] **Step 5: Add the strings**

```python
    "add_product": "Termék hozzáadása",
    "product_qty": "Mennyiség",
    "visit_product_invalid": "Ezt a terméket nem lehet hozzáadni.",
    "visit_total": "Összesen",
```

- [ ] **Step 6: Update `app/templates/visit_close.html`**

First the template needs a way to name a sold product. `VisitItem.product_id`
carries no `ForeignKey` in its column definition (see Deviation 3), so
SQLAlchemy cannot infer the join and the relationship has to spell it out. In
`app/models.py`, next to the existing `treatment` relationship on `VisitItem`:

```python
    product: Mapped["Product | None"] = relationship(
        lazy="joined", viewonly=True,
        primaryjoin="foreign(VisitItem.product_id) == Product.id")
```

`viewonly=True` because nothing assigns through it: `add_product` sets
`product_id` directly, and a writable relationship over a `foreign()`
annotation with no real constraint behind it is a trap for whoever tries.
`Product` is defined after `VisitItem` in the file, hence the string form.

Then, inside the close form's `<ul class="list">`, after the treatment lines,
add the product lines and the total. Keep the Done button immediately after the
list and before everything optional: that order is the one thing the spec says
must not change.

```html
    {% for item in visit.items if item.kind == 'product' %}
    <li class="card row">
      <span class="row__main">
        {{ item.product.name }}
        {% if item.qty != 1 %}
        &times; <span class="num">{{ item.qty | qty }}</span>
        {% endif %}
      </span>
      <strong class="price">{{ (item.unit_price_cents * item.qty) | round | int | eur }}</strong>
    </li>
    {% endfor %}
    <li class="row row--total">
      <span class="row__main">{{ S["visit_total"] }}</span>
      <strong class="price">{{ total_cents | eur }}</strong>
    </li>
```

Then in the collapsible block below the Done button, after the add-treatment
`<details>`:

```html
{% if sellable %}
<details class="card stack-top">
  <summary>{{ S["add_product"] }}</summary>
  <form method="post" action="/visits/{{ visit.id }}/products">
    <select name="product_id" required>
      {% for p in sellable %}
      <option value="{{ p.id }}">{{ p.name }} - {{ p.sale_price_cents | eur }}</option>
      {% endfor %}
    </select>
    <label for="qty">{{ S["product_qty"] }}</label>
    <input id="qty" name="qty" inputmode="decimal" value="1">
    <button type="submit" class="secondary">{{ S["add"] }}</button>
  </form>
</details>
{% endif %}
```

and in the removable-lines list lower down, drop the `if item.kind == 'treatment'`
filter so a sold product can be taken off too, showing the product name for
product lines.

- [ ] **Step 7: Run the tests**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests -q

Expected: PASS, 310 tests (305 + 5).

- [ ] **Step 8: Screenshot loop**

`/visits/1/close` at 390px, with and without a product on the visit. Two things
to check in the image: the Done button is still the first thing under the line
list and still full width, and the total row reads as a total rather than as one
more line item (that is what `row--total` is for; add the rule to `app.css`).

- [ ] **Step 9: Commit**

```bash
git add app/services/visits.py app/routers/visits.py app/routers/api.py \
        app/models.py app/templates/visit_close.html app/strings/hu.py \
        app/static/app.css tests/test_visits_routes.py
git commit -m "feat(pedikur): sell a product at the close, and show what the visit comes to"
```

---

### Task 7: Expenses, with the purchase typed once

**Files:**
- Create: `app/services/expenses.py`
- Create: `app/routers/expenses.py`
- Create: `app/templates/expenses.html`
- Modify: `app/main.py`, `app/templates/settings_index.html`, `app/strings/hu.py`
- Test: `tests/test_expenses.py`, `tests/test_expenses_routes.py`

**Interfaces:**
- Consumes: `stock.record`, `products.list_all`, `treatments.parse_price`,
  `stock_routes.parse_qty`.
- Produces:
  - `expenses.CATEGORIES: tuple[str, ...]`
  - `expenses.create(session, date, category, amount_cents, created_by, vendor=None, note=None, lines=()) -> Expense`
    where each line is `(product_id, qty, unit_cost_cents)`
  - `expenses.recent(session, limit=100) -> list[Expense]`
  - `expenses.line_total_cents(session, expense_id) -> int`
  - `expenses.delete(session, expense_id, created_by) -> None`
  - the routes `GET /expenses`, `POST /expenses`, `POST /expenses/{id}/delete`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_expenses.py
import pytest

from app import migrate
from app.db import Database
from app.services import expenses, products, stock


@pytest.fixture
def db(db_path, tmp_path):
    migrate.run(db_path, backup_dir=tmp_path / "backup")
    return Database(db_path)


@pytest.fixture
def lakk(db):
    with db.session() as s:
        return products.create(s, "Lakk", "flakon", created_by="1").id


def test_an_expense_with_no_lines_is_just_an_expense(db):
    with db.session() as s:
        expenses.create(s, "2026-09-12", "rezsi", 4500, created_by="1",
                        vendor="Aram")
    with db.session() as s:
        rows = expenses.recent(s)
        assert len(rows) == 1
        assert rows[0].amount_cents == 4500
        assert expenses.line_total_cents(s, rows[0].id) == 0


def test_a_line_puts_the_stock_on_the_shelf_at_its_real_price(db, lakk):
    """Buying lacquer is money out and stock in, and it is typed once."""
    with db.session() as s:
        expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                        vendor="Nagyker", lines=[(lakk, 2, 1200)])
    with db.session() as s:
        assert stock.quantity(s, lakk) == 2.0
        assert stock.last_cost_cents(s, lakk) == 1200


def test_the_line_total_is_reported_so_a_mismatch_is_visible(db, lakk):
    """Not refused. She may have bought a coffee on the same receipt, and a
    form that rejects the real receipt is a form she stops filling in."""
    with db.session() as s:
        e = expenses.create(s, "2026-09-12", "anyag", 3000, created_by="1",
                            lines=[(lakk, 2, 1200)])
    with db.session() as s:
        assert expenses.line_total_cents(s, e.id) == 2400


def test_an_invented_category_is_refused(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            expenses.create(s, "2026-09-12", "kave", 300, created_by="1")


def test_a_date_that_is_not_a_calendar_date_is_refused(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            expenses.create(s, "12/09/2026", "anyag", 300, created_by="1")


def test_a_negative_amount_is_refused(db):
    with db.session() as s:
        with pytest.raises(ValueError):
            expenses.create(s, "2026-09-12", "anyag", -300, created_by="1")


def test_deleting_an_expense_takes_its_stock_back_off_the_shelf(db, lakk):
    """Otherwise the ledger claims two bottles that were never bought, and
    every later consumption is charged at a price that never existed."""
    with db.session() as s:
        e = expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                            lines=[(lakk, 2, 1200)])
        e_id = e.id
    with db.session() as s:
        expenses.delete(s, e_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, lakk) == 0.0
        assert expenses.recent(s) == []


def test_deleting_is_soft_and_appends_rather_than_erases(db, lakk):
    """The purchase movement stays. Its reversal is another row, because the
    ledger is append-only and a deleted row cannot be audited."""
    from app.models import Expense, StockMovement
    from sqlalchemy import select
    with db.session() as s:
        e = expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                            lines=[(lakk, 2, 1200)])
        e_id = e.id
    with db.session() as s:
        expenses.delete(s, e_id, created_by="1")
    with db.session() as s:
        assert s.get(Expense, e_id).deleted_at is not None
        rows = list(s.scalars(select(StockMovement)
                              .where(StockMovement.expense_id == e_id)))
        assert sorted(r.reason for r in rows) == ["correction", "purchase"]


def test_deleting_twice_does_not_take_the_stock_off_twice(db, lakk):
    with db.session() as s:
        e = expenses.create(s, "2026-09-12", "anyag", 2400, created_by="1",
                            lines=[(lakk, 2, 1200)])
        e_id = e.id
    with db.session() as s:
        expenses.delete(s, e_id, created_by="1")
    with db.session() as s:
        expenses.delete(s, e_id, created_by="1")
    with db.session() as s:
        assert stock.quantity(s, lakk) == 0.0
```

```python
# tests/test_expenses_routes.py
from app.services import expenses, products, stock


def test_the_expense_screen_needs_a_login(client):
    assert client.get("/expenses").status_code in (303, 307)


def test_an_expense_is_recorded_from_the_form(logged_in):
    r = logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "rezsi", "vendor": "Aram",
        "amount_eur": "45,00", "note": ""})
    assert r.status_code == 303
    with logged_in.app.state.db.session() as s:
        assert expenses.recent(s)[0].amount_cents == 4500


def test_a_line_on_the_form_puts_the_goods_into_stock(logged_in):
    with logged_in.app.state.db.session() as s:
        lakk_id = products.create(s, "Lakk", "flakon", created_by="1").id
    logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "anyag", "vendor": "Nagyker",
        "amount_eur": "24,00", "note": "",
        "line_product_id": str(lakk_id), "line_qty": "2",
        "line_cost_eur": "12,00"})
    with logged_in.app.state.db.session() as s:
        assert stock.quantity(s, lakk_id) == 2.0


def test_a_mistyped_amount_writes_nothing_at_all(logged_in):
    r = logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "anyag", "vendor": "",
        "amount_eur": "negyven", "note": ""})
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert expenses.recent(s) == []


def test_a_mistyped_line_leaves_no_expense_behind(logged_in):
    """Either the money and the stock both land, or neither does. A recorded
    expense whose line was silently dropped is the worst of the three."""
    with logged_in.app.state.db.session() as s:
        lakk_id = products.create(s, "Lakk", "flakon", created_by="1").id
    r = logged_in.post("/expenses", data={
        "date": "2026-09-12", "category": "anyag", "vendor": "",
        "amount_eur": "24,00", "note": "",
        "line_product_id": str(lakk_id), "line_qty": "ketto",
        "line_cost_eur": "12,00"})
    assert "error=" in r.headers["location"]
    with logged_in.app.state.db.session() as s:
        assert expenses.recent(s) == []
        assert stock.quantity(s, lakk_id) == 0.0
```

- [ ] **Step 2: Run them to verify they fail**

Run:

    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests/test_expenses.py \
        tests/test_expenses_routes.py -q

Expected: FAIL, `ImportError: cannot import name 'expenses'`

- [ ] **Step 3: Write `app/services/expenses.py`**

```python
"""Money out, and the stock it sometimes brings in.

Category comes from a fixed list rather than free text: free text would give
the dashboard four spellings of one category within two months, and no way to
merge them afterwards. The keys are ASCII and the Hungarian labels live in
app/strings/hu.py.

An expense with no line items is just an expense. An expense with line items is
also a delivery, and typing it once is the whole reason the two live on one
form: the second entry is the one that gets skipped, and after that the shelf
and the database disagree with nothing to notice it.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense, StockMovement
from app.services import stock, timeutil

CATEGORIES = ("anyag", "eszkoz", "berleti_dij", "rezsi", "marketing", "egyeb")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_AMOUNT_CENTS = 1_000_000_00   # a practice, not a building purchase


def create(session: Session, date: str, category: str, amount_cents: int,
           created_by: str, vendor: str | None = None, note: str | None = None,
           lines: Sequence[tuple[int, float, int]] = ()) -> Expense:
    """One expense, plus one inbound Stock Movement per line item.

    All in one session, so a bad line leaves no expense behind. A recorded
    expense whose line was silently dropped is worse than a refused form:
    nothing on any screen would say the stock is short.
    """
    if category not in CATEGORIES:
        raise ValueError(f"not an expense category: {category!r}")
    if not DATE.match(date or ""):
        # Also a CHECK constraint, but an IntegrityError surfaces at commit,
        # after the route has left its try block, and the user sees a 500.
        raise ValueError(f"not a calendar date: {date!r}")
    amount = int(amount_cents)
    if amount < 0:
        raise ValueError("an expense cannot be negative")
    if amount > MAX_AMOUNT_CENTS:
        raise ValueError(f"amount out of range: {amount}")

    expense = Expense(date=date, category=category, amount_cents=amount,
                      vendor=(vendor or "").strip() or None,
                      note=(note or "").strip() or None, created_by=created_by,
                      created_at=timeutil.to_utc_iso(timeutil.local_now()))
    session.add(expense)
    session.flush()
    for product_id, qty, unit_cost_cents in lines:
        if float(qty) <= 0:
            raise ValueError("a purchased quantity has to be positive")
        stock.record(session, product_id, float(qty), "purchase",
                     created_by=created_by,
                     unit_cost_cents=int(unit_cost_cents),
                     expense_id=expense.id)
    return expense


def recent(session: Session, limit: int = 100) -> list[Expense]:
    """Newest first, deleted ones out. No period filter: the dashboard in
    phase 4 is where periods belong, and until then a flat list of the last
    hundred is the whole requirement."""
    return list(session.scalars(
        select(Expense)
        .where(Expense.deleted_at.is_(None))
        .order_by(Expense.date.desc(), Expense.id.desc())
        .limit(limit)))


def line_total_cents(session: Session, expense_id: int) -> int:
    """What the line items add up to, for comparison against the amount.

    Reported, never enforced. She may have bought a coffee on the same
    receipt, and a form that refuses the real receipt is a form she stops
    filling in. The screen shows the difference so it is visible rather than
    silent.
    """
    total = session.scalar(
        select(func.sum(StockMovement.qty * StockMovement.unit_cost_cents))
        .where(StockMovement.expense_id == expense_id,
               StockMovement.reason == "purchase"))
    return int(round(total or 0))


def delete(session: Session, expense_id: int, created_by: str) -> None:
    """Soft delete, and reverse the stock it brought in.

    Without the reversal the ledger keeps claiming two bottles that were never
    bought, and every later consumption is charged at a price that never
    existed.

    The reversal is a new movement, not an edit of the purchase: the ledger is
    append-only, and a row that can be deleted cannot be audited. Idempotent,
    because deleting twice must not take the stock off twice; deleted_at is
    what tells the second call apart.
    """
    expense = session.get(Expense, expense_id)
    if expense is None:
        raise LookupError(f"no expense {expense_id}")
    if expense.deleted_at is not None:
        return
    for row in session.scalars(
            select(StockMovement)
            .where(StockMovement.expense_id == expense_id,
                   StockMovement.reason == "purchase")):
        stock.record(session, row.product_id, -row.qty, "correction",
                     created_by=created_by,
                     unit_cost_cents=row.unit_cost_cents,
                     expense_id=expense_id,
                     note=f"reversal of expense {expense_id}")
    expense.deleted_at = timeutil.to_utc_iso(timeutil.local_now())
    session.flush()
```

- [ ] **Step 4: Add the strings**

```python
    "expenses_title": "Kiadások",
    "settings_expenses": "Kiadások",
    "expense_none": "Még nincs kiadás",
    "expense_new": "Új kiadás",
    "expense_date": "Dátum",
    "expense_vendor": "Hol",
    "expense_amount": "Összeg",
    "expense_category": "Mire",
    "expense_note": "Megjegyzés",
    "expense_line": "Ami bejött a készletbe",
    "expense_line_hint": "Csak ha árut vettél. Enélkül is jó a kiadás.",
    "expense_line_qty": "Mennyiség",
    "expense_line_cost": "Egységár",
    "expense_line_diff": "Tételek eltérnek",
    "expense_date_invalid": "A dátum nem jó, éééé-hh-nn kell.",
    "expense_amount_invalid": "Az összeg nem szám.",
    "expense_category_invalid": "Ilyen kategória nincs.",
    "expense_line_invalid": "A tételsor nem jó, ezért semmit nem mentettem el.",
    "category_anyag": "Anyag",
    "category_eszkoz": "Eszköz",
    "category_berleti_dij": "Bérleti díj",
    "category_rezsi": "Rezsi",
    "category_marketing": "Marketing",
    "category_egyeb": "Egyéb",
```

- [ ] **Step 5: Write `app/routers/expenses.py`**

```python
"""The expense screen. One form: date, vendor, amount, category, note, and
optionally one line item that also brings the goods into stock."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app import security
from app.models import User
from app.routers import stock as stock_routes
from app.services import expenses, products, treatments
from app.strings.hu import S

router = APIRouter(prefix="/expenses")

_ERRORS = frozenset({
    "expense_date_invalid", "expense_amount_invalid",
    "expense_category_invalid", "expense_line_invalid",
})


@router.get("")
def index(request: Request, error: str | None = None,
          user: User = Depends(security.require_user)):
    with request.app.state.db.session() as s:
        rows = expenses.recent(s)
        # Shown so a receipt whose lines do not add up to its total is
        # visible. Not enforced at write time: she may have bought a coffee on
        # the same receipt, and a form that refuses the real receipt is a form
        # she stops filling in.
        line_totals = {e.id: expenses.line_total_cents(s, e.id) for e in rows}
        return request.app.state.templates.TemplateResponse(
            request, "expenses.html",
            {"user": user, "tab": "more", "expenses": rows,
             "line_totals": line_totals,
             "categories": [(c, S[f"category_{c}"])
                            for c in expenses.CATEGORIES],
             "products": products.list_all(s),
             "error": S[error] if error in _ERRORS else None})


@router.post("")
def create(request: Request,
           date: str = Form(...), category: str = Form(...),
           amount_eur: str = Form(...), vendor: str = Form(""),
           note: str = Form(""),
           line_product_id: str = Form(""), line_qty: str = Form(""),
           line_cost_eur: str = Form(""),
           user: User = Depends(security.require_user)):
    try:
        amount = treatments.parse_price(amount_eur)
    except ValueError:
        return _back("expense_amount_invalid")

    lines: list[tuple[int, float, int]] = []
    if line_product_id.strip() and line_qty.strip():
        try:
            lines.append((int(line_product_id),
                          stock_routes.parse_qty(line_qty),
                          treatments.parse_price(line_cost_eur)
                          if line_cost_eur.strip() else 0))
        except ValueError:
            return _back("expense_line_invalid")

    try:
        with request.app.state.db.session() as s:
            expenses.create(s, date, category, amount, created_by=str(user.id),
                            vendor=vendor, note=note, lines=lines)
    except LookupError:
        return _back("expense_line_invalid")
    except ValueError as exc:
        text = str(exc)
        if "calendar date" in text:
            return _back("expense_date_invalid")
        if "category" in text:
            return _back("expense_category_invalid")
        return _back("expense_line_invalid")
    return RedirectResponse("/expenses", status_code=303)


@router.post("/{expense_id}/delete")
def delete(request: Request, expense_id: int,
           user: User = Depends(security.require_user)):
    try:
        with request.app.state.db.session() as s:
            expenses.delete(s, expense_id, created_by=str(user.id))
    except LookupError:
        pass
    return RedirectResponse("/expenses", status_code=303)


def _back(error: str) -> RedirectResponse:
    return RedirectResponse(f"/expenses?error={error}", status_code=303)
```

- [ ] **Step 6: Write `app/templates/expenses.html`**

```html
{% extends "base.html" %}
{% block title %}{{ S["expenses_title"] }}{% endblock %}
{% block heading %}{{ S["expenses_title"] }}{% endblock %}
{% block body %}
{% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}

{% if not expenses %}
<p class="muted">{{ S["expense_none"] }}</p>
{% endif %}

<ul class="list">
  {% for e in expenses %}
  <li class="card row">
    <div class="row__main">
      <strong>{{ e.vendor or S["category_" ~ e.category] }}</strong>
      <div class="muted">
        <span class="num">{{ e.date }}</span>
        &middot; {{ S["category_" ~ e.category] }}
        {% if line_totals[e.id] and line_totals[e.id] != e.amount_cents %}
        <span class="pill">{{ S["expense_line_diff"] }}</span>
        {% endif %}
      </div>
      {% if e.note %}<div class="muted">{{ e.note }}</div>{% endif %}
    </div>
    <strong class="price">{{ e.amount_cents | eur }}</strong>
    <form method="post" action="/expenses/{{ e.id }}/delete">
      <button class="secondary" type="submit">{{ S["remove"] }}</button>
    </form>
  </li>
  {% endfor %}
</ul>

<details class="card stack-top">
  <summary>{{ S["expense_new"] }}</summary>
  <form method="post" action="/expenses">
    <label for="date">{{ S["expense_date"] }}</label>
    <input id="date" name="date" type="date" required>
    <label for="vendor">{{ S["expense_vendor"] }}</label>
    <input id="vendor" name="vendor">
    <label for="amount_eur">{{ S["expense_amount"] }}</label>
    <input id="amount_eur" name="amount_eur" inputmode="decimal" required>
    <label for="category">{{ S["expense_category"] }}</label>
    <select id="category" name="category" required>
      {% for value, label in categories %}
      <option value="{{ value }}">{{ label }}</option>
      {% endfor %}
    </select>
    <label for="note">{{ S["expense_note"] }}</label>
    <input id="note" name="note">

    <fieldset>
      <legend>{{ S["expense_line"] }}</legend>
      <p class="muted">{{ S["expense_line_hint"] }}</p>
      <label for="line_product_id">{{ S["recipe_product"] }}</label>
      <select id="line_product_id" name="line_product_id">
        <option value=""></option>
        {% for p in products %}
        <option value="{{ p.id }}">{{ p.name }} ({{ p.unit }})</option>
        {% endfor %}
      </select>
      <label for="line_qty">{{ S["expense_line_qty"] }}</label>
      <input id="line_qty" name="line_qty" inputmode="decimal">
      <label for="line_cost_eur">{{ S["expense_line_cost"] }}</label>
      <input id="line_cost_eur" name="line_cost_eur" inputmode="decimal">
    </fieldset>

    <button type="submit">{{ S["save"] }}</button>
  </form>
</details>
{% endblock %}
```

One line item per expense, not a repeatable row. A receipt in this practice
carries one kind of goods plus incidentals, the repeatable version needs
JavaScript to add rows, and the app has none. If a real receipt turns out to
need three products, she records three expenses or one expense plus two stock
corrections. `# ponytail: one line per expense, make it repeatable when a real
receipt needs it.`

- [ ] **Step 7: Wire the router and the menu**

In `app/main.py`, the import line already lists `expenses` from Task 3 Step 7;
now add:

```python
app.include_router(expenses.router)
```

In `app/templates/settings_index.html`:

```html
  <li class="card"><a href="/expenses">{{ S["settings_expenses"] }}</a></li>
```

- [ ] **Step 8: Run the tests**

Run:

    docker build -t pedikur-dev . && \
    docker run --rm --user 0 -v "$PWD":/srv -w /srv pedikur-dev \
      python -m pytest -p no:cacheprovider tests -q

Expected: PASS, 324 tests (310 + 9 service + 5 route).

- [ ] **Step 9: Screenshot loop**

`/expenses` at 390px. Check in the image: the `<fieldset>` for the line item
reads as optional rather than required, and the delete button on a row does not
push the amount off the right edge.

- [ ] **Step 10: Commit**

```bash
git add app/services/expenses.py app/routers/expenses.py \
        app/templates/expenses.html app/main.py \
        app/templates/settings_index.html app/strings/hu.py \
        app/static/app.css tests/test_expenses.py tests/test_expenses_routes.py
git commit -m "feat(pedikur): expenses, and the purchase that is typed once"
```

---

### Task 8: Documentation and the deploy

**Files:**
- Modify: `README.md` (the stack readme)
- Modify: `docs/superpowers/specs/2026-09-05-pedikur-design.md` (the phase table)
- Modify: `docs/proxmox/46_Pedicure_Practice_App.md`
- Modify: `/root/homelab/CONTEXT.md` (the Pedikur glossary)

**Interfaces:** none. This task ships what the previous seven built.

- [ ] **Step 1: Mark phase 2 done in the spec's phase table**

The table was corrected when this plan was written (phase 1 had still claimed
"not started" six days after it went live). Only the status cell is left:

```markdown
| 2. Products, Treatment Recipes, stock, expenses | `docs/superpowers/plans/2026-09-12-pedikur-phase2.md` | deployed YYYY-MM-DD |
```

with the real deploy date from Step 9 below.

- [ ] **Step 2: Record the deviations in the spec**

The spec's section 5 data model block still shows `product ... active,
archived_at` and no `sale_price_cents`. Update those two lines and add one
sentence after the model block:

```markdown
`product.active` was dropped during phase 2 in favour of `archived_at` alone,
and `sale_price_cents` was added: she resells a product occasionally, and a
consumable with no sale price must not be addable to a Visit at zero.
`visit_item.product_id` deliberately carries no foreign key, because adding one
to a live SQLite database needs a table rebuild and `PRAGMA foreign_keys`
cannot be changed inside the transaction the migration runner uses.
```

- [ ] **Step 3: Record the partial margin, where phase 4 will read it**

In the spec's Dashboard bullet in section 6, after the sentence about the two
headline numbers, add:

```markdown
The margin is also partial by design: only Treatments that carry a Recipe
contribute to it, and by decision on 2026-09-12 only the expensive materials
get one. Gloves and wipes are in the cash result and not in the margin. Label
it so, or it will be read as though everything consumed were counted.
```

- [ ] **Step 4: Update the stack README**

Add a "Stock and expenses" section after the existing "Tests" section:

```markdown
## Stock and expenses

Stock is not stored. A product's quantity is `SUM(qty)` over `stock_movement`,
which is append-only: a correction is another row, never an edit.

Consumption is posted when a Visit is closed, by reconciling what the Visit's
Treatments should have used against what is already posted for that Visit.
Closing twice therefore posts once, and a Treatment added after the close still
posts its share. Cancelling a closed Visit gives the stock back through the same
function.

Only Treatments with a Recipe consume anything, and only the expensive materials
have one. That is deliberate, and it is why the margin figure is partial.

To check a product's ledger by hand:

    sqlite3 /srv/docker-data/pedikur/db.sqlite \
      "SELECT created_at, reason, qty, unit_cost_cents, visit_id, expense_id
         FROM stock_movement WHERE product_id = 1 ORDER BY id;"
```

- [ ] **Step 5: Update the public doc**

`docs/proxmox/46_Pedicure_Practice_App.md` is published at
https://docs.homelabor.net. Two rules apply there and are not negotiable: no
personal data, and the real subdomain does not appear (use
`your-pedikur.yourdomain.com`). Add a short section describing what phase 2
added, at the level of "what the design decided and why", not a feature list.
The reconcile argument in Task 5 is the interesting part and the part a reader
learns from.

- [ ] **Step 6: Update the glossary**

In `/root/homelab/CONTEXT.md`, under "Pedikur", add **Product**, **Treatment
Recipe** and **Stock Movement** with one sentence each, in the same style as the
existing entries.

- [ ] **Step 7: Verify the docs build**

```bash
cd /root/homelab && mkdocs build --strict 2>&1 | tail -20
```

Expected: no warnings. A link to a file that does not exist aborts a strict
build; this bit once already in this project.

- [ ] **Step 8: Commit**

```bash
git add README.md docs/ CONTEXT.md
git commit -m "docs(pedikur): what phase 2 added, and why the margin is partial"
```

- [ ] **Step 9: STOP, then deploy**

Ask the human before pushing. `CLAUDE.md`: never `git push` unless explicitly
asked.

**Rollback path, stated before the deploy rather than after it:** the migration
takes an automatic pre-migration snapshot into the backup directory before it
touches the schema, and `migrate.py` keeps the last five. If the deploy goes
wrong, redeploy the previous commit in Komodo; migrations are additive, so the
older code tolerates the newer schema and no restore is needed. If the database
itself is damaged, stop the container, copy the newest `pre-migration-*.sqlite`
from `/srv/docker-data/pedikur/backup/` over `db.sqlite`, delete the `-wal` and
`-shm` sidecars next to it, and start the container. That loses every visit
recorded since the deploy, so read the snapshot's timestamp before overwriting
anything.

On approval:

1. `git push`
2. Redeploy the `pedikur` stack in Komodo (the stack uses `pull_policy: build`).
3. Check the migration ran:
   `ssh root@192.168.0.110 'docker logs pedikur --tail 50 | grep -i migrat'`
4. `curl -s http://192.168.0.110:3010/health` must answer `ok`.
5. Check the public route: `curl -sI https://<the pedikur host>/`. A 503 for
   about ten seconds after a redeploy is Pangolin catching up and is expected,
   not a fault. Retry before investigating.
6. Log in and walk the three new screens on a phone-width window.

---

## Definition of done for phase 2

- [ ] `004_phase2.sql` applied to the live database, with the pre-migration
      snapshot present in `/srv/docker-data/pedikur/backup/`.
- [ ] Test suite green at 324 or more, run inside the image.
- [ ] A product can be created with an opening stock, and its quantity on the
      stock screen equals the sum of its movements.
- [ ] A product under its `min_stock` is visibly flagged.
- [ ] A Treatment can be given a Recipe, and closing a Visit that uses it moves
      the stock by exactly `qty / treatments_per_unit`.
- [ ] Closing the same Visit twice moves the stock once. Verified against the
      movement rows, not only against the total.
- [ ] Cancelling a closed Visit returns its stock.
- [ ] A product with a sale price can be sold at the close, its price frozen on
      the Visit Item, and the visit total covers treatments and products.
- [ ] An expense can be recorded with and without a line item, and a line item
      puts stock on the shelf at the price typed.
- [ ] Deleting an expense with a line reverses the stock through a new movement
      rather than by editing the old one.
- [ ] The close screen still opens with the Done button directly under the line
      list, full width, nothing optional above it. This is the one thing that
      may not regress.
- [ ] `mkdocs build --strict` clean, and the public doc carries no real
      subdomain and no personal data.
- [ ] The spec's phase table names this plan and no longer claims phase 1 is
      unstarted.

## What phase 2 deliberately does not deliver

The dashboard. Every number it needs now exists (revenue from
`visit_item`, expenses from `expense`, consumption cost from `stock_movement`),
which is the point: phase 4 can compute cash result and margin from stored
snapshots rather than from today's prices. Nothing in this phase displays a
total for a period, and adding one here would mean shipping a "result" figure
whose expense half had only just started being collected.
