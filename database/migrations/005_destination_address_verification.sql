-- Destination address verification metadata. Apply once after 004.
ALTER TABLE destination
    ADD COLUMN canonical_address VARCHAR(300) NULL AFTER address,
    ADD COLUMN verification_status ENUM('verified', 'unverified')
        NOT NULL DEFAULT 'unverified' AFTER longitude,
    ADD COLUMN verified_at TIMESTAMP NULL AFTER verification_status;

UPDATE destination
SET verification_status = CASE
        WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 'verified'
        ELSE 'unverified'
    END,
    canonical_address = CASE
        WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN address
        ELSE NULL
    END;
