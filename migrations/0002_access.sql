-- Adds a daily throttle column for the "please renew" reminder.
-- NULL = never notified. Stores the date (not datetime) of the last notice.

ALTER TABLE `correctrice`.`user`
    ADD COLUMN `last_expiry_notice` DATE NULL AFTER `expiry_date`;