-- Incomes: salaries, refunds, gifts, sales. Kept apart from expenses, so
-- the expense entry screen, its totals and its CSV are not affected.
-- category is a code from the fixed list in app/routers/incomes.py
-- (salary, refund, gift, sale, other), checked by the API. No CHECK
-- constraint here: adding a code to the list needs no table rebuild.

CREATE TABLE incomes (
    id                  INTEGER PRIMARY KEY,
    client_uuid         TEXT UNIQUE,          -- idempotency key from the client
    amount_cents        INTEGER NOT NULL CHECK (amount_cents > 0),
    income_date         TEXT NOT NULL,
    category            TEXT NOT NULL,
    note                TEXT,
    received_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_by_user_id  INTEGER NOT NULL REFERENCES users(id),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX idx_incomes_date ON incomes(income_date);
