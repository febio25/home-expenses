-- 0.17.0: a recurring expense or income can have a variable amount (a bill,
-- a salary with overtime). The amount stored is then an estimate: the app
-- writes «circa» before it and «~» before the totals that include it. It
-- changes nothing in how an occurrence is registered: the amount is still
-- proposed and can be corrected each time.
ALTER TABLE recurring_expenses ADD COLUMN is_variable INTEGER NOT NULL DEFAULT 0 CHECK (is_variable IN (0, 1));
ALTER TABLE recurring_incomes ADD COLUMN is_variable INTEGER NOT NULL DEFAULT 0 CHECK (is_variable IN (0, 1));
