from flask import Blueprint

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="admin/templates",
    static_folder="admin/static",
)

staff_bp = Blueprint(
    "staff",
    __name__,
    url_prefix="/staff",
    template_folder="staff/templates",
    static_folder="staff/static",
)

user_bp = Blueprint(
    "user",
    __name__,
    url_prefix="/user",
    template_folder="user/templates",
    static_folder="user/static",
)

# Import route modules after creating the Blueprints so their decorators
# register routes on the objects above.
from users.admin import admin  # noqa: E402,F401
from users.staff import staff  # noqa: E402,F401
from users.user import user  # noqa: E402,F401
