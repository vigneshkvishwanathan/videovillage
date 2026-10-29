-- 001: a disc can have several aspect ratios (was one).
-- Run once per database. Back up first.
BEGIN;

-- The old rule only works on a single number, so it goes first.
ALTER TABLE discs DROP CONSTRAINT discs_aspect_ratio_check;

-- Turn each existing value into a one-item list; an empty value becomes an empty list.
ALTER TABLE discs ALTER COLUMN aspect_ratio TYPE NUMERIC(4, 2)[]
    USING CASE WHEN aspect_ratio IS NULL THEN '{}' ELSE ARRAY[aspect_ratio] END;

ALTER TABLE discs RENAME COLUMN aspect_ratio TO aspect_ratios;
ALTER TABLE discs ALTER COLUMN aspect_ratios SET DEFAULT '{}';
ALTER TABLE discs ALTER COLUMN aspect_ratios SET NOT NULL;

-- The same rule, now checked for every number in the list.
ALTER TABLE discs ADD CONSTRAINT aspect_ratios_positive CHECK (0 < ALL (aspect_ratios));

COMMIT;
