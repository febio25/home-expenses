-- 0.15.0: the entry forms show the categories as icons. Each expense
-- category stores the name of its icon (see app/category_icons.py); NULL
-- means none chosen, and the API answers with the default one.
-- The ten initial categories and the Vinted one get theirs here, by their
-- original name: a category renamed or created by hand keeps NULL until an
-- icon is chosen in Impostazioni → Categorie.
ALTER TABLE categories ADD COLUMN icon TEXT;

UPDATE categories SET icon = CASE name_key
    WHEN 'spesa alimentare' THEN 'shopping-cart'
    WHEN 'casa e utenze'    THEN 'home-bolt'
    WHEN 'salute'           THEN 'first-aid-kit'
    WHEN 'auto e trasporti' THEN 'car'
    WHEN 'ristoranti e bar' THEN 'tools-kitchen-2'
    WHEN 'abbigliamento'    THEN 'shirt'
    WHEN 'svago'            THEN 'ticket'
    WHEN 'abbonamenti'      THEN 'repeat'
    WHEN 'regali'           THEN 'gift'
    WHEN 'varie'            THEN 'dots'
END
WHERE icon IS NULL;

UPDATE categories SET icon = 'hanger' WHERE system_key = 'vinted' AND icon IS NULL;
