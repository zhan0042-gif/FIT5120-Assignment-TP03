-- FIT5120 FIREBREAK
-- Iteration 1 initial application database schema

USE fit5120;


-- =========================================================
-- 1. Household
-- =========================================================

CREATE TABLE household (
    household_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    household_name VARCHAR(150) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);


-- =========================================================
-- 2. Household Member
-- =========================================================

CREATE TABLE household_member (
    member_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    household_id BIGINT UNSIGNED NOT NULL,
    member_name VARCHAR(150) NOT NULL,
    age_group VARCHAR(50),
    needs_assistance BOOLEAN NOT NULL DEFAULT FALSE,
    support_needs TEXT,
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
    household_id BIGINT UNSIGNED NOT NULL,
    animal_name VARCHAR(150),
    animal_type VARCHAR(100) NOT NULL,
    support_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_animal_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    INDEX idx_animal_household (household_id)
);


-- =========================================================
-- 4. Transport
-- =========================================================

CREATE TABLE transport (
    transport_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    household_id BIGINT UNSIGNED NOT NULL,
    transport_name VARCHAR(150) NOT NULL,
    transport_type VARCHAR(100),
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
-- Maps household members to vehicles/transport they can drive
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
    household_id BIGINT UNSIGNED NOT NULL,
    destination_name VARCHAR(150) NOT NULL,
    address VARCHAR(255),
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
-- Stores primary / backup transport and destination choices
-- =========================================================

CREATE TABLE household_arrangement (
    arrangement_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    household_id BIGINT UNSIGNED NOT NULL,

    arrangement_type ENUM(
        'transport',
        'destination'
    ) NOT NULL,

    priority_type ENUM(
        'primary',
        'backup'
    ) NOT NULL,

    transport_id BIGINT UNSIGNED,
    destination_id BIGINT UNSIGNED,

    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_arrangement_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_arrangement_transport
        FOREIGN KEY (transport_id)
        REFERENCES transport(transport_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_arrangement_destination
        FOREIGN KEY (destination_id)
        REFERENCES destination(destination_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_arrangement_reference
        CHECK (
            (
                arrangement_type = 'transport'
                AND transport_id IS NOT NULL
                AND destination_id IS NULL
            )
            OR
            (
                arrangement_type = 'destination'
                AND destination_id IS NOT NULL
                AND transport_id IS NULL
            )
        ),

    CONSTRAINT uq_household_arrangement
        UNIQUE (
            household_id,
            arrangement_type,
            priority_type
        ),

    INDEX idx_arrangement_transport (transport_id),
    INDEX idx_arrangement_destination (destination_id)
);


-- =========================================================
-- 8. Responsibility
-- =========================================================

CREATE TABLE responsibility (
    responsibility_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    household_id BIGINT UNSIGNED NOT NULL,
    responsibility_name VARCHAR(200) NOT NULL,
    primary_member_id BIGINT UNSIGNED NOT NULL,
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
        ON DELETE RESTRICT,

    CONSTRAINT fk_responsibility_backup_member
        FOREIGN KEY (backup_member_id)
        REFERENCES household_member(member_id)
        ON DELETE SET NULL,

    INDEX idx_responsibility_household (household_id)
);


-- =========================================================
-- 9. Household Location
-- Stores household coordinates used by the data lookup layer
-- =========================================================

CREATE TABLE household_location (
    location_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    household_id BIGINT UNSIGNED NOT NULL,
    address VARCHAR(255),
    suburb VARCHAR(150),
    postcode VARCHAR(10),
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_location_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    CONSTRAINT uq_household_location
        UNIQUE (household_id),

    CONSTRAINT chk_location_latitude
        CHECK (latitude BETWEEN -90 AND 90),

    CONSTRAINT chk_location_longitude
        CHECK (longitude BETWEEN -180 AND 180)
);


-- =========================================================
-- 10. Basic Scenario Test Run
-- =========================================================

CREATE TABLE test_run (
    test_run_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    household_id BIGINT UNSIGNED NOT NULL,
    scenario_code VARCHAR(100) NOT NULL,
    scenario_name VARCHAR(200) NOT NULL,

    overall_status ENUM(
        'passed',
        'affected',
        'failed'
    ) NOT NULL,

    first_problem TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_test_run_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    INDEX idx_test_run_household (household_id),
    INDEX idx_test_run_created (created_at)
);


-- =========================================================
-- 11. Scenario Test Check Result
-- =========================================================

CREATE TABLE test_check_result (
    check_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    test_run_id BIGINT UNSIGNED NOT NULL,
    check_code VARCHAR(100) NOT NULL,
    check_name VARCHAR(200) NOT NULL,

    check_status ENUM(
        'passed',
        'affected',
        'failed'
    ) NOT NULL,

    result_message TEXT,
    sort_order INT UNSIGNED NOT NULL DEFAULT 0,

    CONSTRAINT fk_check_result_test_run
        FOREIGN KEY (test_run_id)
        REFERENCES test_run(test_run_id)
        ON DELETE CASCADE,

    INDEX idx_check_result_test_run (test_run_id)
);

