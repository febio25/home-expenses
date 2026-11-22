-- Vinted (0.8.0): items bought to resell, or sold from home, each linked to
-- the expense that bought it and to the income that sold it. The money stays
-- in expenses and incomes: an item only points at them, so the household
-- totals, the month summary and the CSV exports include Vinted by themselves,
-- and an amount corrected in "Movimenti" is the item's amount too.

-- The expense category of the section, marked by system_key: it can be
-- renamed, never deactivated or deleted. A category already called "Vinted"
-- (created by hand before 0.8.0) is adopted with its expenses and its place
-- in the list; otherwise one is added at the end.
ALTER TABLE categories ADD COLUMN system_key TEXT;
CREATE UNIQUE INDEX idx_categories_system_key ON categories(system_key)
    WHERE system_key IS NOT NULL;

UPDATE categories SET system_key = 'vinted', is_active = 1 WHERE name_key = 'vinted';
INSERT INTO categories (name, name_key, sort_order, is_active, created_at, system_key)
SELECT 'Vinted', 'vinted',
       (SELECT COALESCE(MAX(sort_order), 0) + 10 FROM categories),
       1, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), 'vinted'
 WHERE NOT EXISTS (SELECT 1 FROM categories WHERE system_key = 'vinted');

CREATE TABLE vinted_items (
    id                  INTEGER PRIMARY KEY,
    client_uuid         TEXT UNIQUE,          -- idempotency key from the client
    title               TEXT NOT NULL,
    note                TEXT,
    listed_on           TEXT NOT NULL,        -- YYYY-MM-DD: on sale since (the purchase date, else the day it was added)
    is_withdrawn        INTEGER NOT NULL DEFAULT 0 CHECK (is_withdrawn IN (0, 1)),
    -- The expense in the Vinted category that bought it (none for things
    -- already at home) and the income in the category "vinted" that sold it.
    -- Deleting either one from "Movimenti" leaves the item without it.
    purchase_expense_id INTEGER UNIQUE REFERENCES expenses(id) ON DELETE SET NULL,
    sale_income_id      INTEGER UNIQUE REFERENCES incomes(id) ON DELETE SET NULL,
    created_by_user_id  INTEGER NOT NULL REFERENCES users(id),
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

-- One photo per item, resized on the phone before upload. Kept in the
-- database so the backup stays a single file. The small columns come first:
-- lists read the token without touching the images.
CREATE TABLE vinted_photos (
    item_id    INTEGER PRIMARY KEY REFERENCES vinted_items(id) ON DELETE CASCADE,
    token      TEXT NOT NULL,                 -- changes with the image: cache key of its address
    created_at TEXT NOT NULL,
    image      BLOB NOT NULL,                 -- JPEG, about 1200 px on the long side
    thumb      BLOB NOT NULL                  -- JPEG, about 160 px, for the lists
);
