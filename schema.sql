CREATE USER IF NOT EXISTS 'printwise_app'@'127.0.0.1'
IDENTIFIED VIA mysql_native_password
USING PASSWORD('choose-a-strong-password');

GRANT SELECT, INSERT, CREATE, ALTER, UPDATE
ON printwise.*
TO 'printwise_app'@'127.0.0.1';

-- MySQL may identify a local connection as 'localhost' instead.
CREATE USER IF NOT EXISTS 'printwise_app'@'localhost'
IDENTIFIED VIA mysql_native_password
USING PASSWORD('choose-a-strong-password');

GRANT SELECT, INSERT, CREATE, ALTER, UPDATE
ON printwise.*
TO 'printwise_app'@'localhost';
