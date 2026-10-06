-- FIREBREAK
-- Australian Fire Danger Rating System (AFDRS) historical data.

CREATE TABLE open_data_fdr_history (
    fdr_history_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    date DATE NOT NULL,
    issued_at DATETIME NOT NULL,

    district VARCHAR(100) NOT NULL,

    rating_code TINYINT UNSIGNED NOT NULL,
    rating_label VARCHAR(20) NOT NULL,

    year SMALLINT UNSIGNED NOT NULL,
    month TINYINT UNSIGNED NOT NULL,
    day_of_year SMALLINT UNSIGNED NOT NULL,

    UNIQUE KEY uq_open_data_fdr_date_district (date, district),

    INDEX idx_open_data_fdr_date (date),
    INDEX idx_open_data_fdr_district (district),
    INDEX idx_open_data_fdr_rating_code (rating_code)
);