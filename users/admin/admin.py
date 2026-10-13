from flask import render_template
from users import admin_bp


@admin_bp.route("/dashboard")
def dashboard():
    return render_template("admin/dashboard.html")


@admin_bp.route("/printshops")
def printshops():
    return render_template("admin/printshops.html")


@admin_bp.route("/accounts")
def accounts():
    return render_template("admin/accounts.html")


@admin_bp.route("/orders")
def orders():
    return render_template("admin/orders.html")