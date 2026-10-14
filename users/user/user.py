from flask import render_template
from users import user_bp
from users.auth import role_required


@user_bp.route("/dashboard")
@role_required("customer")
def dashboard():
    return render_template("user/dashboard.html")


@user_bp.route("/printshops")
@role_required("customer")
def printshops():
    return render_template("user/printshops.html")


@user_bp.route("/orders")
@role_required("customer")
def orders():
    return render_template("user/orders.html")


@user_bp.route("/orders/new")
@role_required("customer")
def new_order():
    return render_template("user/new_order.html")
