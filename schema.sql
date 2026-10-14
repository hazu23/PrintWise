CREATE USER 'printwise_app'@'127.0.0.1'
IDENTIFIED VIA mysql_native_password
USING PASSWORD('choose-a-strong-password');

GRANT SELECT, INSERT, CREATE
ON printwise.*
TO 'printwise_app'@'127.0.0.1';