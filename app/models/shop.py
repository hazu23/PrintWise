"""Print shops and the services each shop offers."""
from app import catalog
from app.db import db
from app.models.base import Model


def _csv(text: str) -> list:
    return [item.strip() for item in (text or "").split(",") if item.strip()]


class PrintShop(Model):
    table = "print_shops"
    columns = (
        "id", "name", "address", "contact_phone", "contact_email", "hours",
        "description", "is_active", "accepting_orders", "created_at", "updated_at",
    )
    defaults = {"is_active": 1, "accepting_orders": 1}

    @property
    def can_receive_orders(self) -> bool:
        return bool(self.is_active) and bool(self.accepting_orders)

    def services(self, only_active: bool = False) -> list:
        conditions = {"shop_id": self.id}
        if only_active:
            conditions["is_active"] = 1
        return Service.filter(order_by="name ASC", **conditions)

    def owners(self) -> list:
        from app.models.user import ShopOwner
        return ShopOwner.filter(order_by="id ASC", shop_id=self.id)

    def order_count(self) -> int:
        return int(db.scalar("SELECT COUNT(*) FROM orders WHERE shop_id = %s", (self.id,)))

    def has_orders(self) -> bool:
        return self.order_count() > 0

    def delete_with_owners(self) -> None:
        """Remove the shop and its owner accounts (only allowed when it has no orders)."""
        with db.transaction():
            db.execute("DELETE FROM users WHERE shop_id = %s AND role = %s", (self.id, "shop_owner"))
            self.delete()


class Service(Model):
    """A kind of job a shop accepts, such as "Document printing" or "Photo printing".

    A service lists which paper sizes, paper types and color modes the shop
    offers for it, and the order form only shows those options.
    """
    table = "services"
    columns = (
        "id", "shop_id", "name", "description", "paper_sizes", "paper_types",
        "color_modes", "is_active", "created_at", "updated_at",
    )
    defaults = {"is_active": 1, "color_modes": "bw,color"}

    @property
    def size_options(self) -> list:
        return _csv(self.paper_sizes)

    @property
    def type_options(self) -> list:
        return _csv(self.paper_types)

    @property
    def color_options(self) -> list:
        return [c for c in _csv(self.color_modes) if c in catalog.COLOR_MODES]

    def offers(self, size: str, paper_type: str, color: str) -> bool:
        return size in self.size_options and paper_type in self.type_options and color in self.color_options

    def to_option_dict(self) -> dict:
        """Data the order form's JavaScript uses to filter the choices."""
        return {
            "id": self.id,
            "sizes": self.size_options,
            "types": self.type_options,
            "colors": self.color_options,
        }
