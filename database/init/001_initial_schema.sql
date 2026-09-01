-- FIT5120 FIREBREAK
-- Iteration 1 initial application database schema

-- =========================================================
-- 1. Household
-- =========================================================

CREATE TABLE household (
    household_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(150),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);


-- =========================================================
-- 2. Household Member
-- =========================================================

CREATE TABLE household_member (
    member_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL UNIQUE,
    household_id BIGINT UNSIGNED NOT NULL,
    display_name VARCHAR(150) NOT NULL,
    is_dependant BOOLEAN NOT NULL DEFAULT FALSE,
    mobility_support_required BOOLEAN NOT NULL DEFAULT FALSE,
    support_notes TEXT,
    relationship VARCHAR(50),
    relationship_other VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_member_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    INDEX idx_member_household (household_id)
);


-- =========================================================
-- 3. Animal
-- =========================================================

CREATE TABLE animal (
    animal_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL UNIQUE,
    household_id BIGINT UNSIGNED NOT NULL,
    display_name VARCHAR(150),
    category VARCHAR(50) NOT NULL,
    animal_type VARCHAR(100) NOT NULL,
    animal_type_other VARCHAR(100),
    quantity INT UNSIGNED NOT NULL DEFAULT 1,
    support_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_animal_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_animal_quantity
        CHECK (quantity >= 1),

    INDEX idx_animal_household (household_id)
);


-- =========================================================
-- 4. Transport
-- =========================================================

CREATE TABLE transport (
    transport_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL UNIQUE,
    household_id BIGINT UNSIGNED NOT NULL,
    transport_type VARCHAR(100) NOT NULL,
    transport_type_other VARCHAR(100),
    display_name VARCHAR(150),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_transport_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    INDEX idx_transport_household (household_id)
);


-- =========================================================
-- 5. Transport Driver
-- Maps household members to transport they can drive/use
-- =========================================================

CREATE TABLE transport_driver (
    transport_id BIGINT UNSIGNED NOT NULL,
    member_id BIGINT UNSIGNED NOT NULL,

    PRIMARY KEY (transport_id, member_id),

    CONSTRAINT fk_transport_driver_transport
        FOREIGN KEY (transport_id)
        REFERENCES transport(transport_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_transport_driver_member
        FOREIGN KEY (member_id)
        REFERENCES household_member(member_id)
        ON DELETE CASCADE,

    INDEX idx_transport_driver_member (member_id)
);


-- =========================================================
-- 6. Destination
-- =========================================================

CREATE TABLE destination (
    destination_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL UNIQUE,
    household_id BIGINT UNSIGNED NOT NULL,
    display_name VARCHAR(150) NOT NULL,
    address VARCHAR(255),
    unit_number VARCHAR(30),
    street_number VARCHAR(30),
    street_name VARCHAR(150),
    suburb_or_locality VARCHAR(150),
    state VARCHAR(3),
    postcode VARCHAR(10),
    country VARCHAR(100) DEFAULT 'Australia',
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_destination_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_destination_latitude
        CHECK (latitude IS NULL OR latitude BETWEEN -90 AND 90),

    CONSTRAINT chk_destination_longitude
        CHECK (longitude IS NULL OR longitude BETWEEN -180 AND 180),

    INDEX idx_destination_household (household_id)
);


-- =========================================================
-- 7. Household Arrangement
-- One current primary/backup arrangement record per household
-- =========================================================

CREATE TABLE household_arrangement (
    household_id BIGINT UNSIGNED PRIMARY KEY,
    has_private_transport BOOLEAN,

    primary_transport_id BIGINT UNSIGNED,
    backup_transport_id BIGINT UNSIGNED,

    primary_destination_id BIGINT UNSIGNED,
    backup_destination_id BIGINT UNSIGNED,

    meeting_point VARCHAR(255),
    notes TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_arrangement_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_arrangement_primary_transport
        FOREIGN KEY (primary_transport_id)
        REFERENCES transport(transport_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_arrangement_backup_transport
        FOREIGN KEY (backup_transport_id)
        REFERENCES transport(transport_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_arrangement_primary_destination
        FOREIGN KEY (primary_destination_id)
        REFERENCES destination(destination_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_arrangement_backup_destination
        FOREIGN KEY (backup_destination_id)
        REFERENCES destination(destination_id)
        ON DELETE SET NULL,

    INDEX idx_arrangement_primary_transport (primary_transport_id),
    INDEX idx_arrangement_backup_transport (backup_transport_id),
    INDEX idx_arrangement_primary_destination (primary_destination_id),
    INDEX idx_arrangement_backup_destination (backup_destination_id)
);


-- =========================================================
-- 8. Responsibility
-- =========================================================

CREATE TABLE responsibility (
    responsibility_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL UNIQUE,
    household_id BIGINT UNSIGNED NOT NULL,
    task_name VARCHAR(200) NOT NULL,
    primary_member_id BIGINT UNSIGNED,
    backup_member_id BIGINT UNSIGNED,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_responsibility_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_responsibility_primary_member
        FOREIGN KEY (primary_member_id)
        REFERENCES household_member(member_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_responsibility_backup_member
        FOREIGN KEY (backup_member_id)
        REFERENCES household_member(member_id)
        ON DELETE SET NULL,

    INDEX idx_responsibility_household (household_id),
    INDEX idx_responsibility_primary_member (primary_member_id),
    INDEX idx_responsibility_backup_member (backup_member_id)
);


-- =========================================================
-- 9. Household Location
-- Stores household coordinates used by the Data layer
-- =========================================================

CREATE TABLE household_location (
    household_id BIGINT UNSIGNED PRIMARY KEY,
    address VARCHAR(300) NOT NULL,
    canonical_address VARCHAR(300) NULL,
    suburb VARCHAR(150),
    postcode VARCHAR(10),
    unit_number VARCHAR(30),
    street_number VARCHAR(30),
    street_name VARCHAR(150),
    suburb_or_locality VARCHAR(150),
    state VARCHAR(3) NOT NULL DEFAULT 'VIC',
    country VARCHAR(100) NOT NULL DEFAULT 'Australia',
    latitude DECIMAL(9,6) NULL,
    longitude DECIMAL(9,6) NULL,
    verification_status ENUM('verified', 'unverified') NOT NULL DEFAULT 'unverified',
    verified_at TIMESTAMP NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_location_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_location_latitude
        CHECK (latitude BETWEEN -90 AND 90),

    CONSTRAINT chk_location_longitude
        CHECK (longitude BETWEEN -180 AND 180)
);


-- =========================================================
-- 10. Derived Household Location Context
-- One cached GeoParquet result per verified household location.
-- =========================================================

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


-- =========================================================
-- 11. Basic Scenario Test Run
-- =========================================================

CREATE TABLE test_run (
    test_run_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL UNIQUE,
    household_id BIGINT UNSIGNED NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,

    overall_status ENUM(
        'pass',
        'needs_attention'
    ) NOT NULL,

    result_reason TEXT,
    first_problem_section VARCHAR(50),
    first_problem_message TEXT,
    tested_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),

    CONSTRAINT fk_test_run_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    INDEX idx_test_run_household (household_id),
    INDEX idx_test_run_tested_at (tested_at)
);


-- =========================================================
-- 12. Scenario Test Check Result
-- =========================================================

CREATE TABLE test_check_result (
    check_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    test_run_id BIGINT UNSIGNED NOT NULL,
    check_order SMALLINT UNSIGNED NOT NULL,
    check_code VARCHAR(100) NOT NULL,

    status ENUM(
        'pass',
        'fail',
        'not_checked'
    ) NOT NULL,

    message TEXT,

    CONSTRAINT fk_check_result_test_run
        FOREIGN KEY (test_run_id)
        REFERENCES test_run(test_run_id)
        ON DELETE CASCADE,

    CONSTRAINT uq_check_result_order
        UNIQUE (test_run_id, check_order),

    INDEX idx_check_result_test_run (test_run_id)
);
