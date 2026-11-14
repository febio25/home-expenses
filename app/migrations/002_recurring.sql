-- Recurring expense templates (subscriptions, bills).
-- A template never creates expenses by itself: when next_due is reached the
-- app shows it as "da registrare" and a person confirms it, possibly with a
-- different amount. Confirming or skipping moves next_due forward.

CREATE TABLE recurring_expenses (
    id               INTEGER PRIMARY KEY,
    amount_cents     INTEGER NOT NULL CHECK (amount_cents > 0),   -- proposed amount
    category_id      INTEGER NOT NULL REFERENCES categories(id),
    merchant_name    TEXT,                     -- text, resolved when registering
    note             TEXT,
    paid_by_user_id  INTEGER NOT NULL REFERENCES users(id),
    payment_method   TEXT NOT NULL CHECK (payment_method IN ('card', 'cash', 'other')),
    interval_months  INTEGER NOT NULL CHECK (interval_months BETWEEN 1 AND 12),
    day_of_month     INTEGER NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),  -- 31 = last day
    next_due         TEXT NOT NULL,            -- YYYY-MM-DD of the next occurrence
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE INDEX idx_recurring_next_due ON recurring_expenses(next_due);
