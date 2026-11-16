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
