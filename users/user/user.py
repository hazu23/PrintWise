from flask import render_template
from users import user_bp


@user_bp.route("/dashboard")
def dashboard():
    return render_template("user/dashboard.html")


@user_bp.route("/printshops")
def printshops():
    return render_template("user/printshops.html")


@user_bp.route("/orders")
def orders():
    return render_template("user/orders.html")


@user_bp.route("/orders/new")
def new_order():
    return render_template("user/new_order.html")
