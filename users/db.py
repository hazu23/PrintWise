# 

from flask import current_app, g
# current_app - it's the current flask app handling the request
# g - temp storage for the request
import pymysql
from pymysql.cursors import DictCursor  # imports mymysql dictionary cursor


def get_db():
    if "db" not in g:                                       # checks flask’s tempo storage, g, to see if this request already has a database connection
        # Flask's g storage keeps this connection available during the request.
        g.db = pymysql.connect(                             # if there isn’t one, it connects to MySQL and saves the connection in g.db
            host=current_app.config["DB_HOST"],             # where mysql is running (host & port)
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],         # which database to use
            charset="utf8mb4",
            cursorclass=DictCursor,  # returns rows that can be accessed by column name
        )
    return g.db


def close_db(error=None):
    # Close the request's database connection when the request ends
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db():
    # Create the accounts table if it does not exist yet
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

        # Older versions created users without a username column. Update those databases here.
        cursor.execute("SHOW COLUMNS FROM users LIKE 'username'")
        username_column = cursor.fetchone()
        if username_column is None:
            # Add it as optional first because existing rows do not have usernames yet.
            cursor.execute("ALTER TABLE users ADD COLUMN username VARCHAR(30) NULL AFTER name")
            # Give existing users a temporary unique username based on their id.
            cursor.execute("UPDATE users SET username = CONCAT('user', id) WHERE username IS NULL")
            # Now every row has a value, so make usernames required and unique.
            cursor.execute("ALTER TABLE users MODIFY username VARCHAR(30) NOT NULL")
            cursor.execute("ALTER TABLE users ADD UNIQUE (username)")

    database.commit()
