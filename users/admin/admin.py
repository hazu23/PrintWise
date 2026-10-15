from flask import render_template
from users import admin_bp
from users.auth import role_required


@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    return render_template("admin/dashboard.html")

@admin_bp.route("/orders")
@role_required("admin")
def orders():
    return render_template("admin/orders.html")
