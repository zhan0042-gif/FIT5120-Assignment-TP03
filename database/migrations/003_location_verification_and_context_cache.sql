-- FIREBREAK I1 location persistence and derived-context cache upgrade.
-- Apply once after 002. Existing location rows are retained and backfilled.

ALTER TABLE household_location
    ADD COLUMN canonical_address VARCHAR(300) NULL AFTER address,
    MODIFY COLUMN latitude DECIMAL(9,6) NULL,
    MODIFY COLUMN longitude DECIMAL(9,6) NULL,
    ADD COLUMN verification_status ENUM('verified', 'unverified')
        NOT NULL DEFAULT 'unverified' AFTER longitude,
    ADD COLUMN verified_at TIMESTAMP NULL AFTER verification_status;

UPDATE household_location
SET canonical_address = address,
    verification_status = 'verified',
    verified_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;

CREATE TABLE household_location_context (
    household_id BIGINT UNSIGNED PRIMARY KEY,
    is_bushfire_prone_area BOOLEAN NOT NULL,
    fire_district VARCHAR(100) NOT NULL,
    fire_history_record_count INT UNSIGNED NULL,
    fire_history_latest_year SMALLINT UNSIGNED NULL,
    fire_history_latest_date DATE NULL,
    fire_history_radius_km DECIMAL(6,2) NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_location_context_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE
);
