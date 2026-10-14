"""Small MySQL helpers for the PrintWise student project."""

from flask import current_app, g
import pymysql
from pymysql.cursors import DictCursor


def get_db():
    """Open one MySQL connection for the current web request."""
    if "db" not in g:
        g.db = pymysql.connect(
            host=current_app.config["DB_HOST"],
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],
            charset="utf8mb4",
            cursorclass=DictCursor,
        )
    return g.db


def close_db(error=None):
    """Close the request's database connection when the request ends."""
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db():
    """Create the accounts table if it does not exist yet."""
    database = get_db()
    with database.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'customer'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    database.commit()
