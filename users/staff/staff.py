from flask import render_template
from users import staff_bp


@staff_bp.route("/dashboard")
def dashboard():
    return render_template("staff/dashboard.html")


@staff_bp.route("/orders")
def orders():
    return render_template("staff/orders.html")


@staff_bp.route("/services")
def services():
    return render_template("staff/services.html")


@staff_bp.route("/quotations")
def quotations():
    return render_template("staff/quotations.html")
