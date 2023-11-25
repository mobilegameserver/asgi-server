
-- DROP DATABASE `users`;
CREATE DATABASE `users` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- DROP USER 'user1'@'localhost';
CREATE USER 'user1'@'localhost' IDENTIFIED BY 'password1';
GRANT ALL PRIVILEGES ON `users`.* TO 'user1'@'localhost';
FLUSH PRIVILEGES;

USE `users`;

CREATE TABLE `migrations` (`migration_id` BIGINT NOT NULL DEFAULT 0, PRIMARY KEY (`migration_id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO `migrations` VALUES (19700101000000);
