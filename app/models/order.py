"""Orders, their status history, payments recorded at the counter, and sales reports."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from app import catalog
from app.db import db, now
from app.models.base import Model, money


class OrderStatusLog(Model):
    table = "order_status_log"
    columns = ("id", "order_id", "status", "note", "changed_by", "created_at")


class Transaction(Model):
    """Money received for an order. It is recorded by the shop when the customer picks up."""
    table = "transactions"
    columns = (
        "id", "receipt_no", "order_id", "shop_id", "amount", "method",
        "received_by", "note", "created_at",
    )
    defaults = {"method": "cash"}

    @property
    def method_label(self) -> str:
        return catalog.PAYMENT_METHODS.get(self.method, self.method)

    @classmethod
    def search(cls, shop_id, start=None, end=None, method=None, limit=None, offset=0):
        """Transactions of one shop, newest first, with order and customer details."""
        where, params = ["t.shop_id = %s"], [shop_id]
        if start:
            where.append("t.created_at >= %s")
            params.append(start)
        if end:
            where.append("t.created_at < %s")
            params.append(end)
        if method in catalog.PAYMENT_METHODS:
            where.append("t.method = %s")
            params.append(method)
        base = (" FROM transactions t JOIN orders o ON o.id = t.order_id"
                " JOIN users u ON u.id = o.customer_id WHERE " + " AND ".join(where))
        total = int(db.scalar("SELECT COUNT(*)" + base, params))
        amount = money(db.scalar("SELECT SUM(t.amount)" + base, params))
        sql = ("SELECT t.*, o.order_no AS order_no, o.id AS order_ref, u.full_name AS customer_name"
               + base + " ORDER BY t.id DESC")
        if limit is not None:
            sql += " LIMIT %s OFFSET %s"
            params = params + [int(limit), int(offset)]
        return cls.select(sql, params), total, amount


class Order(Model):
    table = "orders"
    columns = (
        "id", "order_no", "customer_id", "shop_id", "service_id", "service_name",
        "paper_size", "paper_type", "color_mode", "sides", "copies", "pages", "notes",
        "file_name", "file_stored", "file_size", "status", "status_note",
        "created_at", "updated_at", "completed_at",
    )
    defaults = {"status": "pending", "copies": 1, "sides": "single", "file_size": 0}

    # The steps an order moves through, in order. This list drives the tracker on screen.
    STAGES = (
        ("pending", "Submitted"),
        ("accepted", "Accepted"),
        ("printing", "Printing"),
        ("ready", "Ready for pickup"),
        ("completed", "Completed"),
    )
    LABELS = {**dict(STAGES), "rejected": "Declined", "cancelled": "Cancelled"}
    # What the shop may do next from each status.
    SHOP_TRANSITIONS = {
        "pending": ("accepted", "rejected"),
        "accepted": ("printing", "ready", "rejected"),
        "printing": ("ready",),
        "ready": ("completed",),
    }
    OPEN_STATUSES = ("pending", "accepted", "printing", "ready")
    CLOSED_STATUSES = ("completed", "rejected", "cancelled")

    # ----- display helpers ---------------------------------------------------
    @property
    def status_label(self) -> str:
        return self.LABELS.get(self.status, self.status)

    @property
    def stage_index(self) -> int:
        """Position in STAGES (0-4), or -1 when the order was declined or cancelled."""
        keys = [key for key, _ in self.STAGES]
        return keys.index(self.status) if self.status in keys else -1

    @property
    def color_label(self) -> str:
        return catalog.COLOR_MODES.get(self.color_mode, self.color_mode)

    @property
    def sides_label(self) -> str:
        return catalog.SIDES.get(self.sides, self.sides)

    @property
    def spec_summary(self) -> str:
        return f"{self.paper_size}, {self.paper_type}, {self.color_label}, {self.sides_label}"

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES

    # ----- what each side may do ------------------------------------------------
    @property
    def customer_can_edit(self) -> bool:
        return self.status == "pending"

    @property
    def customer_can_cancel(self) -> bool:
        return self.status == "pending"

    @property
    def customer_can_delete(self) -> bool:
        return self.status in ("cancelled", "rejected")

    def shop_options(self) -> tuple:
        return self.SHOP_TRANSITIONS.get(self.status, ())

    # ----- lookups ---------------------------------------------------------
    @classmethod
    def search(cls, shop_id=None, customer_id=None, status=None, q=None,
               start=None, end=None, limit=12, offset=0):
        """Filterable list of orders with the customer and shop names attached."""
        where, params = [], []
        if shop_id:
            where.append("o.shop_id = %s")
            params.append(shop_id)
        if customer_id:
            where.append("o.customer_id = %s")
            params.append(customer_id)
        if status == "open":
            where.append("o.status IN (%s, %s, %s, %s)")
            params += list(cls.OPEN_STATUSES)
        elif status in cls.LABELS:
            where.append("o.status = %s")
            params.append(status)
        if q:
            like = f"%{q}%"
            where.append("(o.order_no LIKE %s OR o.file_name LIKE %s OR o.service_name LIKE %s OR u.full_name LIKE %s)")
            params += [like, like, like, like]
        if start:
            where.append("o.created_at >= %s")
            params.append(start)
        if end:
            where.append("o.created_at < %s")
            params.append(end)
        base = (" FROM orders o JOIN users u ON u.id = o.customer_id JOIN print_shops s ON s.id = o.shop_id"
                + (" WHERE " + " AND ".join(where) if where else ""))
        total = int(db.scalar("SELECT COUNT(*)" + base, params))
        sql = ("SELECT o.*, u.full_name AS customer_name, u.username AS customer_username,"
               " s.name AS shop_name" + base + " ORDER BY o.id DESC LIMIT %s OFFSET %s")
        return cls.select(sql, params + [int(limit), int(offset)]), total

    @classmethod
    def counts_by_status(cls, shop_id=None, customer_id=None) -> dict:
        where, params = [], []
        if shop_id:
            where.append("shop_id = %s")
            params.append(shop_id)
        if customer_id:
            where.append("customer_id = %s")
            params.append(customer_id)
        sql = "SELECT status, COUNT(*) AS n FROM orders" + (" WHERE " + " AND ".join(where) if where else "") + " GROUP BY status"
        counts = {key: 0 for key in cls.LABELS}
        for row in db.query(sql, params):
            counts[row["status"]] = int(row["n"])
        return counts

    # ----- related records ---------------------------------------------------
    @property
    def customer(self):
        from app.models.user import User
        return User.get(self.customer_id)

    @property
    def shop(self):
        from app.models.shop import PrintShop
        return PrintShop.get(self.shop_id)

    @property
    def transaction(self):
        return Transaction.find_by(order_id=self.id)

    def history(self) -> list:
        return OrderStatusLog.filter(order_by="id ASC", order_id=self.id)

    # ----- actions ---------------------------------------------------------
    def _log(self, status, actor_id, note=None):
        OrderStatusLog(order_id=self.id, status=status, note=note, changed_by=actor_id).save()

    def place(self, actor_id) -> "Order":
        """Save a brand-new order, give it its number and record the first status."""
        with db.transaction():
            self.save()
            self.order_no = f"PW-{now():%y%m}-{self.id:05d}"
            self.save()
            self._log("pending", actor_id, "Order submitted")
        return self

    def change_status(self, new_status: str, actor_id, note: str = None) -> "Order":
        """Shop moves the order forward (or declines it). Illegal jumps are refused."""
        if new_status not in self.shop_options() or new_status == "completed":
            raise ValueError(f"Cannot move an order from '{self.status}' to '{new_status}'.")
        with db.transaction():
            self.status = new_status
            self.status_note = note if new_status == "rejected" else None
            self.save()
            self._log(new_status, actor_id, note)
        return self

    def cancel(self, actor_id) -> "Order":
        if not self.customer_can_cancel:
            raise ValueError("Only orders that have not been accepted can be cancelled.")
        with db.transaction():
            self.status = "cancelled"
            self.save()
            self._log("cancelled", actor_id, "Cancelled by customer")
        return self

    def complete_with_payment(self, amount, method: str, actor_id, note: str = None) -> Transaction:
        """Record the payment taken at the counter and close the order."""
        if self.status != "ready":
            raise ValueError("Only orders that are ready for pickup can be completed.")
        if method not in catalog.PAYMENT_METHODS:
            raise ValueError("Unknown payment method.")
        with db.transaction():
            payment = Transaction(order_id=self.id, shop_id=self.shop_id, amount=money(amount),
                                  method=method, received_by=actor_id, note=note).save()
            payment.receipt_no = f"OR-{payment.id:06d}"
            payment.save()
            self.status = "completed"
            self.completed_at = now()
            self.save()
            self._log("completed", actor_id, f"Paid {money(amount)} by {catalog.PAYMENT_METHODS[method]}")
        return payment


class SalesReport:
    """Totals for one shop over a date range, worked out from recorded transactions."""

    def __init__(self, shop_id: int, start: datetime, end: datetime):
        self.shop_id, self.start, self.end = shop_id, start, end
        rows, _, _ = Transaction.search(shop_id, start, end)
        self.transactions = rows

    @property
    def total(self) -> Decimal:
        return sum((money(t.amount) for t in self.transactions), Decimal("0.00"))

    @property
    def count(self) -> int:
        return len(self.transactions)

    @property
    def average(self) -> Decimal:
        return (self.total / self.count).quantize(Decimal("0.01")) if self.count else Decimal("0.00")

    def by_method(self) -> list:
        totals = {}
        for t in self.transactions:
            totals[t.method] = totals.get(t.method, Decimal("0.00")) + money(t.amount)
        return sorted(((catalog.PAYMENT_METHODS.get(k, k), v) for k, v in totals.items()),
                      key=lambda item: item[1], reverse=True)

    def by_day(self) -> list:
        """One entry per day in the range (including days with no sales)."""
        per_day = {}
        for t in self.transactions:
            day = t.created_at.date()
            total, n = per_day.get(day, (Decimal("0.00"), 0))
            per_day[day] = (total + money(t.amount), n + 1)
        days, cursor = [], self.start.date()
        while cursor < self.end.date():
            total, n = per_day.get(cursor, (Decimal("0.00"), 0))
            days.append({"day": cursor, "total": total, "count": n})
            cursor += timedelta(days=1)
        return days


def day_bounds(day: date) -> tuple:
    """Start (inclusive) and end (exclusive) of a calendar day."""
    start = datetime(day.year, day.month, day.day)
    return start, start + timedelta(days=1)
