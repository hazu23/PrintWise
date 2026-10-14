"""Database access layer.

`Database` is the only place that talks to the database driver. Every query is
written with %s placeholders and the values are passed separately, so user input
is never pasted into SQL text (this is what protects the app from SQL injection).

MySQL (via PyMySQL) is the real database. SQLite is supported only so the
automated tests can run without a MySQL server.
"""
import re
import sqlite3
from decimal import Decimal
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import current_app, g

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "database" / "schema.sql"

# Tables from children to parents, so they can be dropped without foreign key errors.
TABLE_DROP_ORDER = [
    "notifications", "inventory_logs", "inventory_items", "transactions",
    "order_status_log", "orders", "services", "users", "print_shops",
]

# --- SQLite helpers (tests only): store/read datetimes as plain text -----------
sqlite3.register_adapter(datetime, lambda d: d.strftime("%Y-%m-%d %H:%M:%S"))
sqlite3.register_adapter(Decimal, str)
sqlite3.register_converter("DATETIME", lambda b: datetime.strptime(b.decode(), "%Y-%m-%d %H:%M:%S"))


def now() -> datetime:
    """Current local time (Philippine time by default) as a naive datetime."""
    offset = current_app.config.get("TIMEZONE_OFFSET_HOURS", 8)
    return datetime.now(timezone(timedelta(hours=offset))).replace(tzinfo=None, microsecond=0)


class Database:
    """Thin wrapper around one database connection per request."""

    # ----- connection handling ----------------------------------------------
    def init_app(self, app):
        app.teardown_appcontext(self.close)

    @property
    def backend(self) -> str:
        return current_app.config["DB_BACKEND"]

    def _connect(self):
        cfg = current_app.config
        if self.backend == "sqlite":
            conn = sqlite3.connect(cfg["SQLITE_PATH"], detect_types=sqlite3.PARSE_DECLTYPES)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        import pymysql  # imported here so tests do not need it
        from pymysql.cursors import DictCursor
        return pymysql.connect(
            host=cfg["DB_HOST"], port=cfg["DB_PORT"], user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"],
            charset="utf8mb4", cursorclass=DictCursor, autocommit=False,
        )

    @property
    def connection(self):
        if "db_conn" not in g:
            g.db_conn = self._connect()
            g.db_depth = 0
        return g.db_conn

    def close(self, _exc=None):
        conn = g.pop("db_conn", None)
        if conn is not None:
            conn.close()

    # ----- running SQL ------------------------------------------------------
    def _sql(self, sql: str) -> str:
        return sql.replace("%s", "?") if self.backend == "sqlite" else sql

    def _run(self, sql: str, params=()):
        cur = self.connection.cursor()
        try:
            cur.execute(self._sql(sql), tuple(params))
        except Exception:
            self.connection.rollback()
            raise
        return cur

    @staticmethod
    def _to_dict(row):
        return dict(row) if row is not None else None

    def query(self, sql: str, params=()) -> list:
        """SELECT many rows -> list of dicts."""
        cur = self._run(sql, params)
        rows = [self._to_dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def query_one(self, sql: str, params=()):
        """SELECT one row -> dict or None."""
        cur = self._run(sql, params)
        row = self._to_dict(cur.fetchone())
        cur.close()
        return row

    def scalar(self, sql: str, params=(), default=0):
        row = self.query_one(sql, params)
        if not row:
            return default
        value = next(iter(row.values()))
        return default if value is None else value

    def execute(self, sql: str, params=()) -> int:
        """INSERT / UPDATE / DELETE. Returns the new id for inserts, else affected rows."""
        cur = self._run(sql, params)
        result = cur.lastrowid if sql.lstrip().upper().startswith("INSERT") else cur.rowcount
        cur.close()
        if g.db_depth == 0:
            self.connection.commit()
        return result

    @contextmanager
    def transaction(self):
        """Group several writes so they all succeed or all fail together."""
        conn = self.connection
        g.db_depth += 1
        try:
            yield
        except Exception:
            g.db_depth -= 1
            if g.db_depth == 0:
                conn.rollback()
            raise
        else:
            g.db_depth -= 1
            if g.db_depth == 0:
                conn.commit()

    # ----- schema -----------------------------------------------------------
    def _schema_statements(self) -> list:
        sql = SCHEMA_FILE.read_text(encoding="utf-8")
        sql = re.sub(r"--[^\n]*", "", sql)  # strip comments
        if self.backend == "sqlite":
            sql = re.sub(r"id INT UNSIGNED NOT NULL AUTO_INCREMENT,", "id INTEGER PRIMARY KEY AUTOINCREMENT,", sql)
            sql = re.sub(r"\n\s*PRIMARY KEY \(id\),?", "", sql)
            sql = re.sub(r"\)\s*ENGINE=[^;]*;", ");", sql)
            sql = re.sub(r",(\s*)\)", r"\1)", sql)
        return [s.strip() for s in sql.split(";") if s.strip()]

    def create_schema(self):
        for statement in self._schema_statements():
            self._run(statement)
        self.connection.commit()

    def drop_schema(self):
        conn = self.connection
        if self.backend != "sqlite":
            self._run("SET FOREIGN_KEY_CHECKS = 0")
        for table in TABLE_DROP_ORDER:
            self._run(f"DROP TABLE IF EXISTS {table}")
        if self.backend != "sqlite":
            self._run("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()


db = Database()
