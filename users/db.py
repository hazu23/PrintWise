# i might switch to mysql-connector-python as connector for mysql in the future

from flask import current_app, g 
    ## current_app - it's the current flask app handling the request
    ## g - temp storage for the request
import pymysql
from pymysql.cursors import DictCursor # imports mymysql dictionary cursor


def get_db():
    """open one MySQL connection for the current web request"""
    if "db" not in g:                                       # checks flask’s tempo storage, g, to see if this request already has a database connection
        g.db = pymysql.connect(                             # if there isn’t one, it connects to MySQL and saves the connection in g.db
            host=current_app.config["DB_HOST"],             # where mysql is running (host & port)
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],             
            password=current_app.config["DB_PASSWORD"],
            database=current_app.config["DB_NAME"],         #which database to use
            charset="utf8mb4",
            cursorclass=DictCursor,                         # returns rows that can be accessed by column name
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
