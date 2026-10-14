"""Shop inventory (paper, ink, supplies) and the stock notifications users see."""
from app import catalog
from app.db import db
from app.models.base import Model


class InventoryLog(Model):
    table = "inventory_logs"
    columns = ("id", "item_id", "change_qty", "quantity_after", "reason", "changed_by", "created_at")


class InventoryItem(Model):
    """A stock item. Quantities are changed by hand, because shops are too busy to count every sheet."""
    table = "inventory_items"
    columns = (
        "id", "shop_id", "name", "category", "unit", "quantity", "low_stock_level",
        "notes", "created_at", "updated_at",
    )
    defaults = {"category": "paper", "unit": "sheets", "quantity": 0, "low_stock_level": 0}

    @property
    def category_label(self) -> str:
        return catalog.INVENTORY_CATEGORIES.get(self.category, self.category)

    @property
    def is_low(self) -> bool:
        return self.quantity <= self.low_stock_level

    @property
    def is_out(self) -> bool:
        return self.quantity <= 0

    def adjust(self, change: int, reason: str, actor_id) -> "InventoryItem":
        """Add (positive) or remove (negative) stock and keep a log entry."""
        if self.quantity + change < 0:
            raise ValueError("There is not enough stock to remove that amount.")
        with db.transaction():
            self.quantity += change
            self.save()
            InventoryLog(item_id=self.id, change_qty=change, quantity_after=self.quantity,
                         reason=reason, changed_by=actor_id).save()
        return self

    def logs(self, limit: int = 20) -> list:
        return InventoryLog.filter(order_by="id DESC", limit=limit, item_id=self.id)

    @classmethod
    def low_stock_for(cls, shop_id: int) -> list:
        return cls.select(
            "SELECT * FROM inventory_items WHERE shop_id = %s AND quantity <= low_stock_level ORDER BY quantity ASC",
            (shop_id,))


class Notification(Model):
    table = "notifications"
    columns = ("id", "user_id", "title", "message", "link", "is_read", "created_at")
    defaults = {"is_read": 0}

    @classmethod
    def for_user(cls, user_id: int, limit: int = 50) -> list:
        return cls.filter(order_by="id DESC", limit=limit, user_id=user_id)

    @classmethod
    def mark_all_read(cls, user_id: int) -> None:
        db.execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (user_id,))
