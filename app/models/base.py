"""Base class for every database-backed object (the "parent" of all models).

A model is a Python class that represents one table. Each row becomes an
object, and the class carries the behaviour that belongs to that kind of thing
(for example `User.check_password` or `Order.advance`).

Child classes only declare their table name and column list; the generic
create / read / update / delete code lives here once (inheritance).
"""
from decimal import Decimal

from app.db import db, now


class Model:
    table: str = ""
    columns: tuple = ()
    hidden: tuple = ()          # columns never included in to_dict()
    fixed: dict = {}            # conditions every query of this class adds (e.g. role)
    defaults: dict = {}

    # ----- construction ----------------------------------------------------
    def __init__(self, **values):
        defaults = {"id": None, **self.defaults, **self.fixed}
        for column in self.columns:
            default = defaults.get(column)
            setattr(self, column, values.get(column, default() if callable(default) else default))
        # Extra values (for example columns joined from another table).
        for key, value in values.items():
            if key not in self.columns:
                setattr(self, key, value)

    @classmethod
    def from_row(cls, row):
        return cls(**row) if row else None

    # ----- reading ---------------------------------------------------------
    @classmethod
    def _where(cls, conditions: dict):
        conditions = {**conditions, **cls.fixed}
        for key in conditions:
            if key not in cls.columns:  # whitelist: column names never come from user input
                raise ValueError(f"Unknown column: {key}")
        if not conditions:
            return "", []
        clause = " AND ".join(f"{key} = %s" for key in conditions)
        return " WHERE " + clause, list(conditions.values())

    @classmethod
    def get(cls, record_id):
        if record_id is None:
            return None
        return cls.find_by(id=record_id)

    @classmethod
    def find_by(cls, **conditions):
        rows = cls.filter(limit=1, **conditions)
        return rows[0] if rows else None

    @classmethod
    def filter(cls, order_by: str = "id DESC", limit: int = None, offset: int = 0, **conditions):
        where, params = cls._where(conditions)
        sql = f"SELECT * FROM {cls.table}{where}"
        sql += cls._order_clause(order_by)
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params += [int(limit), int(offset)]
        return [cls.from_row(r) for r in db.query(sql, params)]

    @classmethod
    def _order_clause(cls, order_by: str) -> str:
        """Only allow "column [ASC|DESC]" built from known columns."""
        parts = []
        for chunk in order_by.split(","):
            tokens = chunk.split()
            if not tokens or tokens[0] not in cls.columns:
                raise ValueError("Invalid ordering")
            direction = tokens[1].upper() if len(tokens) > 1 else "ASC"
            if direction not in ("ASC", "DESC"):
                raise ValueError("Invalid ordering")
            parts.append(f"{tokens[0]} {direction}")
        return " ORDER BY " + ", ".join(parts)

    @classmethod
    def count(cls, **conditions) -> int:
        where, params = cls._where(conditions)
        return int(db.scalar(f"SELECT COUNT(*) FROM {cls.table}{where}", params))

    @classmethod
    def select(cls, sql: str, params=()):
        """Run a custom SELECT and wrap each row in this class."""
        return [cls.from_row(r) for r in db.query(sql, params)]

    # ----- writing ---------------------------------------------------------
    def save(self):
        """INSERT when the object is new, otherwise UPDATE it."""
        stamp = now()
        if "created_at" in self.columns and getattr(self, "created_at", None) is None:
            self.created_at = stamp
        if "updated_at" in self.columns:
            self.updated_at = stamp
        if self.id is None:
            names = [c for c in self.columns if c != "id"]
            marks = ", ".join(["%s"] * len(names))
            sql = f"INSERT INTO {self.table} ({', '.join(names)}) VALUES ({marks})"
            self.id = db.execute(sql, [getattr(self, c) for c in names])
        else:
            names = [c for c in self.columns if c != "id"]
            assignments = ", ".join(f"{c} = %s" for c in names)
            sql = f"UPDATE {self.table} SET {assignments} WHERE id = %s"
            db.execute(sql, [getattr(self, c) for c in names] + [self.id])
        return self

    def delete(self):
        if self.id is not None:
            db.execute(f"DELETE FROM {self.table} WHERE id = %s", (self.id,))

    # ----- output ----------------------------------------------------------
    def to_dict(self) -> dict:
        return {c: getattr(self, c) for c in self.columns if c not in self.hidden}

    def __repr__(self):
        return f"<{type(self).__name__} id={getattr(self, 'id', None)}>"


def money(value) -> Decimal:
    """Turn a database number (Decimal in MySQL, float in SQLite) into a Decimal."""
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))
