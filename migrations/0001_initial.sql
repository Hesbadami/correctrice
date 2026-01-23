CREATE DATABASE `correctrice` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_0900_ai_ci;


CREATE TABLE IF NOT EXISTS `correctrice`.`user` (
    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `user_id` VARCHAR(255) UNIQUE NOT NULL,
    `first_name` VARCHAR(255) NOT NULL,
    `last_name` VARCHAR(255),
    `email` VARCHAR(255) AFTER `last_name`,
    `expiry_date` DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS `correctrice`.`task` (

    `id` BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    `user_id` BIGINT UNSIGNED NOT NULL,

    `message_id` BIGINT,
    `file_id` VARCHAR(255),
    `transcription` TEXT,
    `correction` TEXT,

    `cost` INT,
    `status` ENUM('pending', 'downloading', 'transcribing', 'correcting', 'complete'),
    `error_message` TEXT,

    `date_created` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    `date_modified` DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),

    `correlation_status` ENUM('pending', 'processing', 'done', 'failed') DEFAULT 'pending',
    `correlation_id` CHAR(36) NULL,

    FOREIGN KEY (`user_id`) REFERENCES `user`(`id`) ON DELETE CASCADE,

    INDEX idx_task_corr (`correlation_id`),
    INDEX idx_user_id (`user_id`, `status`),
    INDEX idx_user_corr (`user_id`, `correlation_status`),
    INDEX idx_corr_stat (`correlation_status`, `status`)
);