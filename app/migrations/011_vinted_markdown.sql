-- 0.19.0 (F7): the markdown plan of an item on sale, a step down every few
-- days until the minimum, always confirmed by hand. No plan of its own
-- (markdown_kind NULL) means the base plan of the app (10% every 14 days):
-- changing the base later changes those items too, without a migration.
-- markdown_kind: 'pct' (markdown_amount is a percentage), 'eur' (cents) or
-- 'none' (never marked down). markdown_source: who chose the plan, 'claude'
-- (read from the answer) or 'manual'. markdown_skipped_on: the last «Salta»
-- (the next step counts from then); markdown_settled_on: «Lascia così» at
-- the minimum (no more reminders until the price changes again).
ALTER TABLE vinted_items ADD COLUMN markdown_kind TEXT CHECK (markdown_kind IN ('pct', 'eur', 'none'));
ALTER TABLE vinted_items ADD COLUMN markdown_amount INTEGER CHECK (markdown_amount > 0);
ALTER TABLE vinted_items ADD COLUMN markdown_days INTEGER CHECK (markdown_days > 0);
ALTER TABLE vinted_items ADD COLUMN markdown_source TEXT CHECK (markdown_source IN ('claude', 'manual'));
ALTER TABLE vinted_items ADD COLUMN markdown_skipped_on TEXT;
ALTER TABLE vinted_items ADD COLUMN markdown_settled_on TEXT;
