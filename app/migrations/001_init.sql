-- Initial schema. Timestamps are ISO 8601 UTC strings, dates are YYYY-MM-DD.

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,      -- case-folded login key
    display_name  TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE sessions (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   TEXT NOT NULL UNIQUE,       -- SHA-256 of the session token
    created_at   TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    expires_at   TEXT NOT NULL
);

CREATE TABLE categories (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    name_key   TEXT NOT NULL UNIQUE,         -- case-folded, for uniqueness
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE merchants (
    id         INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    name_key   TEXT NOT NULL UNIQUE,         -- trimmed, single-spaced, case-folded
    created_at TEXT NOT NULL
);

CREATE TABLE expenses (
    id                 INTEGER PRIMARY KEY,
    client_uuid        TEXT UNIQUE,          -- idempotency key from the client
    amount_cents       INTEGER NOT NULL CHECK (amount_cents > 0),
    expense_date       TEXT NOT NULL,
    category_id        INTEGER NOT NULL REFERENCES categories(id),
    merchant_id        INTEGER REFERENCES merchants(id),
    note               TEXT,
    paid_by_user_id    INTEGER NOT NULL REFERENCES users(id),
    payment_method     TEXT NOT NULL CHECK (payment_method IN ('card', 'cash', 'other')),
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE INDEX idx_expenses_date ON expenses(expense_date);
CREATE INDEX idx_expenses_merchant ON expenses(merchant_id, created_at);
CREATE INDEX idx_expenses_category ON expenses(category_id);
CREATE INDEX idx_sessions_user ON sessions(user_id);

INSERT INTO categories (name, name_key, sort_order, created_at) VALUES
    ('Spesa alimentare',  'spesa alimentare',  10,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Casa e utenze',     'casa e utenze',     20,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Salute',            'salute',            30,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Auto e trasporti',  'auto e trasporti',  40,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Ristoranti e bar',  'ristoranti e bar',  50,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Abbigliamento',     'abbigliamento',     60,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Svago',             'svago',             70,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Abbonamenti',       'abbonamenti',       80,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Regali',            'regali',            90,  strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    ('Varie',             'varie',             100, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
