-- FIREBREAK
-- Open spatial data storage for database-backed location context.

-- =========================================================
-- 1. Bushfire Prone Area
-- =========================================================

CREATE TABLE open_data_bpa (
    bpa_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    lga_code VARCHAR(20) NULL,
    lga_name VARCHAR(150) NULL,
    geometry GEOMETRY NOT NULL SRID 4326,

    SPATIAL INDEX idx_open_data_bpa_geometry (geometry),
    INDEX idx_open_data_bpa_lga_code (lga_code)
);


-- =========================================================
-- 2. CFA Fire District
-- =========================================================

CREATE TABLE open_data_fire_district (
    fire_district_id SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    fire_district VARCHAR(100) NOT NULL UNIQUE,
    geometry GEOMETRY NOT NULL SRID 4326,

    SPATIAL INDEX idx_open_data_fire_district_geometry (geometry)
);


-- =========================================================
-- 3. Historical Fire - lightweight runtime dataset
-- =========================================================

CREATE TABLE open_data_fire_history (
    fire_history_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    season SMALLINT UNSIGNED NULL,
    start_date DATE NULL,
    geometry POINT NOT NULL SRID 4326,

    SPATIAL INDEX idx_open_data_fire_history_geometry (geometry),
    INDEX idx_open_data_fire_history_season (season),
    INDEX idx_open_data_fire_history_start_date (start_date)
);