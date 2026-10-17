# this code is for connection to MySQL, closing the connection and preparing the database tables and printshops

from flask import current_app, g
# current_app - it's the current flask app handling the request. it's config contains database host, port, username, password and database name.
# g - temp storage for the request associated with the current flask app. can be reused
import pymysql
# pymysql is the python library used to connect to MySQL and run SQL.
from pymysql.cursors import DictCursor
# imports pymysql dictionary cursor

def get_db():
    if "db" not in g:                                       
        # this function checks if the current context already has a connection in g.db
        # If it does, the function returns that existing connection.
        # If it doesn’t, the function opens one with pymysql.connect() and stores it in g.db before returning it.
        g.db = pymysql.connect(
            host=current_app.config["DB_HOST"],
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],         # which database to use
            charset="utf8mb4",
            cursorclass=DictCursor,  # means query results can be read by column name.
        )
    return g.db


def close_db(error=None):
    # Close the request's database connection when the request ends
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db():
    # Creates the accounts table if it does not exist yet
    database = get_db()
    with database.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                username VARCHAR(30) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'customer'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )

        cursor.execute("SHOW COLUMNS FROM users LIKE 'username'")
        username_column = cursor.fetchone()
        if username_column is None:
            cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(30) NULL AFTER name")
            cursor.execute("UPDATE users SET username = CONCAT('user', id) WHERE username IS NULL")
            cursor.execute("ALTER TABLE users MODIFY username VARCHAR(30) NOT NULL")
            cursor.execute("ALTER TABLE users ADD UNIQUE (username)")

        # Create a table for printshops customers can browse.
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS printshops (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                description VARCHAR(500) NOT NULL,
                location VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )

        # Add sample listings the first time the printshop table is created.
        cursor.execute("SELECT COUNT(*) AS shop_count FROM printshops")
        shop_count = cursor.fetchone()["shop_count"]
        if shop_count == 0:
            cursor.executemany(
                "INSERT INTO printshops (name, description, location) VALUES (%s, %s, %s)",
                [
                    (
                        "Demo Printshop One",
                        "Sample listing. Replace this with details for a real printshop.",
                        "Example location",
                    ),
                    (
                        "Demo Printshop Two",
                        "Sample listing. Add the shop's printing services and specialties here later.",
                        "Example location",
                    ),
                    (
                        "Demo Printshop Three",
                        "Sample listing. This shop is here to help preview the directory page.",
                        "Example location",
                    ),
                ],
            )

    database.commit()
