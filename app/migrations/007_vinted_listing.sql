-- Vinted listings (0.10.0): what an ad on Vinted needs, written with Claude
-- by hand (the app prepares the request and reads the answer back; it never
-- calls anything outside). All optional; codes and limits are checked by the
-- API (app/schemas.py: VINTED_KINDS, VINTED_CONDITIONS), as for the income
-- categories, so a new code needs no rebuilt table.
ALTER TABLE vinted_items ADD COLUMN kind TEXT;                -- clothing, bag, book, other: decides the fields shown
ALTER TABLE vinted_items ADD COLUMN brand TEXT;
ALTER TABLE vinted_items ADD COLUMN size TEXT;
ALTER TABLE vinted_items ADD COLUMN condition TEXT;           -- new_with_tags, new_without_tags, very_good, good, satisfactory
ALTER TABLE vinted_items ADD COLUMN color_material TEXT;
ALTER TABLE vinted_items ADD COLUMN measurements TEXT;
ALTER TABLE vinted_items ADD COLUMN book_author TEXT;
ALTER TABLE vinted_items ADD COLUMN book_publisher_year TEXT;
ALTER TABLE vinted_items ADD COLUMN defects TEXT;
ALTER TABLE vinted_items ADD COLUMN similar_prices TEXT;      -- prices seen on Vinted for similar items, as typed
ALTER TABLE vinted_items ADD COLUMN listing_title TEXT;
ALTER TABLE vinted_items ADD COLUMN listing_description TEXT;
ALTER TABLE vinted_items ADD COLUMN price_cents INTEGER;      -- asking price on Vinted, now
ALTER TABLE vinted_items ADD COLUMN min_price_cents INTEGER;  -- not below this

-- The asking price on Vinted over time: the first row is the price on the
-- day it was published, then one row per day the price changed. Only for
-- items on Vinted: taking an item back to "Da pubblicare" clears it.
CREATE TABLE vinted_price_changes (
    id          INTEGER PRIMARY KEY,
    item_id     INTEGER NOT NULL REFERENCES vinted_items(id) ON DELETE CASCADE,
    price_cents INTEGER NOT NULL,
    changed_on  TEXT NOT NULL,                -- YYYY-MM-DD
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_vinted_price_changes_item ON vinted_price_changes(item_id, changed_on, id);
