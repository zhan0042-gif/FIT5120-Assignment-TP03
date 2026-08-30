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
    public_id VARCHAR(64) NOT NULL UNIQUE,
    household_id BIGINT UNSIGNED NOT NULL,
    transport_type VARCHAR(100) NOT NULL,
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
    address VARCHAR(300),
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
    public_id VARCHAR(64) NOT NULL UNIQUE,
    household_id BIGINT UNSIGNED NOT NULL,
    scenario_id VARCHAR(100) NOT NULL,

    overall_status ENUM(
        'pass',
        'needs_attention'
    ) NOT NULL,

    result_reason TEXT,
    tested_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_test_run_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,

    INDEX idx_test_run_household (household_id),
    INDEX idx_test_run_tested_at (tested_at)
);


-- =========================================================
-- 11. Scenario Test Check Result
-- =========================================================

CREATE TABLE test_check_result (
    check_result_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    test_run_id BIGINT UNSIGNED NOT NULL,
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

    INDEX idx_check_result_test_run (test_run_id)
);
