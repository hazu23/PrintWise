"""User accounts.

`User` holds everything the three kinds of account share. `Customer`,
`ShopOwner` and `Admin` inherit from it and override only what is different
(their home page, their label). Loading a row through `User` automatically
returns the right subclass, so the rest of the code can simply call
`user.home_endpoint()` without checking the role (polymorphism).
"""
from datetime import timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from app.db import db, now
from app.models.base import Model

HASH_METHOD = "pbkdf2:sha256"


class User(Model):
    table = "users"
    columns = (
        "id", "role", "username", "email", "full_name", "phone", "password_hash",
        "avatar_filename", "shop_id", "email_verified", "is_active", "must_change_password",
        "failed_logins", "locked_until", "last_login_at", "created_at", "updated_at",
    )
    hidden = ("password_hash", "failed_logins", "locked_until")
    defaults = {
        "role": "customer", "email_verified": 0, "is_active": 1,
        "must_change_password": 0, "failed_logins": 0,
    }
    role_label = "User"

    # ----- password handling (encapsulation) --------------------------------
    # Callers never touch `password_hash` directly; they use these two methods.
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password, method=HASH_METHOD)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash or "", raw_password or "")

    # ----- lookups ---------------------------------------------------------
    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        target = cls if cls is not User else ROLE_CLASSES.get(row.get("role"), User)
        return target(**row)

    @classmethod
    def find_by_login(cls, identifier: str):
        """Find an account by username or email (case-insensitive)."""
        identifier = (identifier or "").strip().lower()
        rows = cls.select("SELECT * FROM users WHERE username = %s OR email = %s LIMIT 1",
                          (identifier, identifier))
        return rows[0] if rows else None

    @classmethod
    def username_taken(cls, username: str, except_id=None) -> bool:
        row = db.query_one("SELECT id FROM users WHERE username = %s", (username.lower(),))
        return bool(row) and row["id"] != except_id

    @classmethod
    def email_taken(cls, email: str, except_id=None) -> bool:
        row = db.query_one("SELECT id FROM users WHERE email = %s", (email.lower(),))
        return bool(row) and row["id"] != except_id

    # ----- login protection ------------------------------------------------
    def is_locked(self) -> bool:
        return bool(self.locked_until) and self.locked_until > now()

    def minutes_until_unlock(self) -> int:
        if not self.is_locked():
            return 0
        return max(1, int((self.locked_until - now()).total_seconds() // 60) + 1)

    def register_failed_login(self, max_attempts: int, lock_minutes: int) -> None:
        self.failed_logins = (self.failed_logins or 0) + 1
        if self.failed_logins >= max_attempts:
            self.locked_until = now() + timedelta(minutes=lock_minutes)
            self.failed_logins = 0
        self.save()

    def register_successful_login(self) -> None:
        self.failed_logins = 0
        self.locked_until = None
        self.last_login_at = now()
        self.save()

    # ----- behaviour that differs by role -----------------------------------
    def home_endpoint(self) -> str:
        return "public.index"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_shop_owner(self) -> bool:
        return self.role == "shop_owner"

    @property
    def is_customer(self) -> bool:
        return self.role == "customer"

    # ----- helpers ---------------------------------------------------------
    @property
    def first_name(self) -> str:
        return (self.full_name or "").split(" ")[0]

    @property
    def initials(self) -> str:
        parts = (self.full_name or "?").split()
        return "".join(p[0] for p in parts[:2]).upper()

    @property
    def shop(self):
        if not self.shop_id:
            return None
        if not hasattr(self, "_shop_cache"):
            from app.models.shop import PrintShop
            self._shop_cache = PrintShop.get(self.shop_id)
        return self._shop_cache

    def unread_notifications(self) -> int:
        return int(db.scalar("SELECT COUNT(*) FROM notifications WHERE user_id = %s AND is_read = 0", (self.id,)))


class Customer(User):
    fixed = {"role": "customer"}
    role_label = "Customer"

    def home_endpoint(self) -> str:
        return "customer.dashboard"


class ShopOwner(User):
    fixed = {"role": "shop_owner"}
    role_label = "Shop owner"

    def home_endpoint(self) -> str:
        return "shop.dashboard"


class Admin(User):
    fixed = {"role": "admin"}
    role_label = "Administrator"

    def home_endpoint(self) -> str:
        return "admin.dashboard"


ROLE_CLASSES = {"customer": Customer, "shop_owner": ShopOwner, "admin": Admin}
