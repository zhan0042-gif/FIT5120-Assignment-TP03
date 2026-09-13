-- 008_member_usual_location.sql
-- Adds the declared day-to-day location used by the rendezvous simulation.
-- All columns are nullable: existing plans are unaffected.
--
-- These are user-declared hypothetical locations for simulation, not tracked
-- positions. Handled at the same sensitivity as the household address.

ALTER TABLE household_member
    ADD COLUMN usual_location_kind        VARCHAR(20)   NULL,
    ADD COLUMN usual_location_address     VARCHAR(255)  NULL,
    ADD COLUMN usual_latitude             DECIMAL(9,6)  NULL,
    ADD COLUMN usual_longitude            DECIMAL(9,6)  NULL,
    ADD COLUMN usual_verification_status  VARCHAR(20)   NULL;
