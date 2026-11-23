-- Merchants that look alike but are different places (0.11.0): the pairs
-- marked «Non sono doppioni» in Impostazioni → Esercenti, so they are not
-- offered as possible duplicates again, to either user. One row per pair,
-- the smaller id first. Merging or deleting a merchant drops its pairs.
CREATE TABLE merchant_distinct_pairs (
    merchant_a_id      INTEGER NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    merchant_b_id      INTEGER NOT NULL REFERENCES merchants(id) ON DELETE CASCADE,
    created_by_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at         TEXT NOT NULL,
    PRIMARY KEY (merchant_a_id, merchant_b_id),
    CHECK (merchant_a_id < merchant_b_id)
);
CREATE INDEX idx_merchant_distinct_pairs_b ON merchant_distinct_pairs(merchant_b_id);
