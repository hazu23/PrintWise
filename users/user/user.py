from flask import render_template
from users import user_bp
from users.auth import role_required
from users.db import get_db


@user_bp.route("/dashboard")
@role_required("customer")
def dashboard():
    return render_template("user/dashboard.html")

@user_bp.route("/printshops")
@role_required("customer")
def printshops():
    with get_db().cursor() as cursor:
        cursor.execute(
            "SELECT id, name, description, location "
            "FROM printshops WHERE is_active = TRUE ORDER BY name"
        )
        printshops = cursor.fetchall()

    return render_template("user/printshops.html", printshops=printshops)

@user_bp.route("/orders")
@role_required("customer")
def orders():
    return render_template("user/orders.html")

@user_bp.route("/orders/new")
@role_required("customer")
def new_order():
    return render_template("user/new_order.html")
