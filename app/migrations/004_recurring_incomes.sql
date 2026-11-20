-- Recurring income templates (salaries, fixed transfers), the twin of
-- recurring_expenses. Same rules: a template never creates incomes by
-- itself; when next_due is reached the app shows it as "da registrare" and
-- a person confirms it, possibly with a different amount. Confirming or
-- skipping moves next_due forward. A table of its own, so the expense
-- templates are not touched.

CREATE TABLE recurring_incomes (
    id                  INTEGER PRIMARY KEY,
    amount_cents        INTEGER NOT NULL CHECK (amount_cents > 0),   -- proposed amount
    category            TEXT NOT NULL,             -- code of INCOME_CATEGORIES, checked by the API
    note                TEXT,
    received_by_user_id INTEGER NOT NULL REFERENCES users(id),
    interval_months     INTEGER NOT NULL CHECK (interval_months BETWEEN 1 AND 12),
    day_of_month        INTEGER NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),  -- 31 = last day
    next_due            TEXT NOT NULL,             -- YYYY-MM-DD of the next occurrence
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE INDEX idx_recurring_incomes_next_due ON recurring_incomes(next_due);
