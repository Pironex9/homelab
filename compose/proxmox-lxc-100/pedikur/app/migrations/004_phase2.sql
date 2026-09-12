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
