from flask import Blueprint

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder="admin/templates"
)

staff_bp = Blueprint(
    "staff",
    __name__,
    url_prefix="/staff",
    template_folder="staff/templates"
)

user_bp = Blueprint(
    "user",
    __name__,
    url_prefix="/user",
    template_folder="user/templates"
)
