-- Vinted (0.10.0): an item can wait before it goes on Vinted ("Da pubblicare").
-- listed_on becomes optional: NULL = not on Vinted yet, otherwise the day it
-- was published there. The items already recorded keep their date and stay
-- "In vendita".
--
-- SQLite cannot drop NOT NULL from a column in place. Rebuilding the table
-- is not an option either: with foreign keys on, DROP TABLE vinted_items
-- would delete every photo (vinted_photos has ON DELETE CASCADE). So: a new
-- column, a copy, then the old column dropped and the new one renamed
-- (DROP COLUMN needs SQLite 3.35 or later).
ALTER TABLE vinted_items ADD COLUMN listed_on_new TEXT;  -- YYYY-MM-DD, or NULL: not on Vinted yet
UPDATE vinted_items SET listed_on_new = listed_on;
ALTER TABLE vinted_items DROP COLUMN listed_on;
ALTER TABLE vinted_items RENAME COLUMN listed_on_new TO listed_on;
