-- FIREBREAK I1 data-model upgrade for existing MySQL 8.4 databases.
-- Apply once to the configured application database. Existing rows are retained.

ALTER TABLE household_member
    ADD COLUMN relationship VARCHAR(50) NULL AFTER support_notes,
    ADD COLUMN relationship_other VARCHAR(100) NULL AFTER relationship;

ALTER TABLE animal
    ADD COLUMN animal_type_other VARCHAR(100) NULL AFTER animal_type,
    ADD COLUMN quantity INT UNSIGNED NOT NULL DEFAULT 1 AFTER animal_type_other,
    ADD CONSTRAINT chk_animal_quantity CHECK (quantity >= 1);

-- Preserve non-canonical legacy types as an explicit custom value.
UPDATE animal
SET animal_type_other = animal_type,
    animal_type = 'other'
WHERE LOWER(TRIM(animal_type)) NOT IN (
    'dog', 'cat', 'bird', 'rabbit', 'reptile',
    'horse', 'cattle', 'sheep', 'goat', 'alpaca', 'poultry', 'other'
);

UPDATE animal
SET animal_type_other = animal_type,
    animal_type = 'other'
WHERE (category = 'pet' AND LOWER(TRIM(animal_type)) NOT IN (
          'dog', 'cat', 'bird', 'rabbit', 'reptile', 'other'
      ))
   OR (category = 'livestock' AND LOWER(TRIM(animal_type)) NOT IN (
          'horse', 'cattle', 'sheep', 'goat', 'alpaca', 'poultry', 'other'
      ));

UPDATE animal SET animal_type = LOWER(TRIM(animal_type));

ALTER TABLE transport
    ADD COLUMN transport_type_other VARCHAR(100) NULL AFTER transport_type;

ALTER TABLE destination
    ADD COLUMN unit_number VARCHAR(30) NULL AFTER address,
    ADD COLUMN street_number VARCHAR(30) NULL AFTER unit_number,
    ADD COLUMN street_name VARCHAR(150) NULL AFTER street_number,
    ADD COLUMN suburb_or_locality VARCHAR(150) NULL AFTER street_name,
    ADD COLUMN state VARCHAR(3) NULL AFTER suburb_or_locality,
    ADD COLUMN postcode VARCHAR(10) NULL AFTER state,
    ADD COLUMN country VARCHAR(100) NULL DEFAULT 'Australia' AFTER postcode;

ALTER TABLE household_location
    ADD COLUMN unit_number VARCHAR(30) NULL AFTER postcode,
    ADD COLUMN street_number VARCHAR(30) NULL AFTER unit_number,
    ADD COLUMN street_name VARCHAR(150) NULL AFTER street_number,
    ADD COLUMN suburb_or_locality VARCHAR(150) NULL AFTER street_name,
    ADD COLUMN state VARCHAR(3) NOT NULL DEFAULT 'VIC' AFTER suburb_or_locality,
    ADD COLUMN country VARCHAR(100) NOT NULL DEFAULT 'Australia' AFTER state;

UPDATE household_location
SET suburb_or_locality = suburb
WHERE suburb_or_locality IS NULL AND suburb IS NOT NULL;
