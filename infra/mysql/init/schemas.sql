CREATE DATABASE IF NOT EXISTS `user`;
CREATE DATABASE IF NOT EXISTS `event`;
CREATE DATABASE IF NOT EXISTS `venue`;
CREATE DATABASE IF NOT EXISTS `equipment`;
CREATE DATABASE IF NOT EXISTS `registration`;
CREATE DATABASE IF NOT EXISTS `notification`;

GRANT ALL PRIVILEGES ON `user`.* TO 'connectsphere'@'%';
GRANT ALL PRIVILEGES ON `event`.* TO 'connectsphere'@'%';
GRANT ALL PRIVILEGES ON `venue`.* TO 'connectsphere'@'%';
GRANT ALL PRIVILEGES ON `equipment`.* TO 'connectsphere'@'%';
GRANT ALL PRIVILEGES ON `registration`.* TO 'connectsphere'@'%';
GRANT ALL PRIVILEGES ON `notification`.* TO 'connectsphere'@'%';
