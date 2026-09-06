-- Phase 1 tables. Times are ISO-8601 UTC text, except working_hours.start
-- and working_hours.end which are wall-clock "HH:MM" and must never be
-- timezone-converted. Money is integer cents, EUR.

CREATE TABLE user (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    failed_logins INTEGER NOT NULL DEFAULT 0,
    locked_until  TEXT
);

CREATE TABLE client (
    id                     INTEGER PRIMARY KEY,
    name                   TEXT NOT NULL,
    phone                  TEXT,
    email                  TEXT,
    address                TEXT,
    alert                  TEXT,   -- health warning, shown only inside the card
    notes                  TEXT,
    interval_override_days INTEGER,
    archived_at            TEXT,
    erased_at              TEXT,
    created_by             TEXT NOT NULL,
    created_at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_client_name ON client (name);

CREATE TABLE treatment (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    duration_min INTEGER NOT NULL,
    price_cents  INTEGER NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    created_by   TEXT    NOT NULL
);

CREATE TABLE visit (
    id         INTEGER PRIMARY KEY,
    client_id  INTEGER NOT NULL REFERENCES client (id),
    starts_at  TEXT    NOT NULL,   -- ISO-8601 UTC
    ends_at    TEXT    NOT NULL,   -- ISO-8601 UTC, only ever grows on its own
    status     TEXT    NOT NULL DEFAULT 'planned'
               CHECK (status IN ('planned', 'done', 'cancelled', 'no_show')),
    findings   TEXT,               -- what was observed
    note       TEXT,               -- what was done
    deleted_at TEXT,
    created_by TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_visit_window ON visit (starts_at, ends_at);
CREATE INDEX idx_visit_client ON visit (client_id, starts_at);

CREATE TABLE visit_item (
    id               INTEGER PRIMARY KEY,
    visit_id         INTEGER NOT NULL REFERENCES visit (id),
    kind             TEXT    NOT NULL CHECK (kind IN ('treatment', 'product')),
    treatment_id     INTEGER REFERENCES treatment (id),
    product_id       INTEGER,     -- phase 2
    qty              REAL    NOT NULL DEFAULT 1,
    unit_price_cents INTEGER NOT NULL,
    CHECK (
        (kind = 'treatment' AND treatment_id IS NOT NULL AND product_id IS NULL)
        OR
        (kind = 'product' AND product_id IS NOT NULL AND treatment_id IS NULL)
    )
);
CREATE INDEX idx_visit_item_visit ON visit_item (visit_id);

CREATE TABLE working_hours (
    id        INTEGER PRIMARY KEY,
    weekday   INTEGER,        -- 0 = Monday .. 6 = Sunday, the recurring default
    date      TEXT,           -- YYYY-MM-DD, overrides that one day
    start     TEXT NOT NULL,  -- wall clock "HH:MM"
    end       TEXT NOT NULL,  -- wall clock "HH:MM"
    is_closed INTEGER NOT NULL DEFAULT 0,
    CHECK ((weekday IS NULL) <> (date IS NULL))
);
CREATE UNIQUE INDEX idx_working_hours_weekday ON working_hours (weekday)
    WHERE weekday IS NOT NULL;
CREATE UNIQUE INDEX idx_working_hours_date ON working_hours (date)
    WHERE date IS NOT NULL;

CREATE TABLE setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
