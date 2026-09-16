-- FIREBREAK
-- Add historical fire burned area to the lightweight runtime table.

ALTER TABLE open_data_fire_history
ADD COLUMN area_ha DECIMAL(18,6) NULL AFTER start_date;