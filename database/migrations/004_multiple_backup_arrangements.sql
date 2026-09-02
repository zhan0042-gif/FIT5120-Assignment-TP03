-- FIREBREAK I1 normalized multiple-backup arrangements.
-- Apply once after 003. Legacy fixed primary/backup columns remain deprecated
-- for compatibility and are not read or written by the current application.

CREATE TABLE household_arrangement_option (
    arrangement_option_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    household_id BIGINT UNSIGNED NOT NULL,
    role ENUM('primary', 'backup') NOT NULL,
    priority SMALLINT UNSIGNED NOT NULL,
    transport_id BIGINT UNSIGNED NULL,
    destination_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_arrangement_option_household
        FOREIGN KEY (household_id)
        REFERENCES household(household_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_arrangement_option_transport
        FOREIGN KEY (transport_id)
        REFERENCES transport(transport_id)
        ON DELETE SET NULL,
    CONSTRAINT fk_arrangement_option_destination
        FOREIGN KEY (destination_id)
        REFERENCES destination(destination_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_arrangement_option_role_priority
        CHECK (
            (role = 'primary' AND priority = 0)
            OR (role = 'backup' AND priority >= 1)
        ),
    UNIQUE KEY uq_arrangement_option_role_priority (household_id, role, priority),
    INDEX idx_arrangement_option_transport (transport_id),
    INDEX idx_arrangement_option_destination (destination_id)
);

INSERT INTO household_arrangement_option (
    household_id, role, priority, transport_id, destination_id
)
SELECT household_id, 'primary', 0, primary_transport_id, primary_destination_id
FROM household_arrangement
WHERE primary_transport_id IS NOT NULL OR primary_destination_id IS NOT NULL;

INSERT INTO household_arrangement_option (
    household_id, role, priority, transport_id, destination_id
)
SELECT household_id, 'backup', 1, backup_transport_id, backup_destination_id
FROM household_arrangement
WHERE backup_transport_id IS NOT NULL OR backup_destination_id IS NOT NULL;
