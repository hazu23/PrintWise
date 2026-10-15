from flask import render_template
from users import staff_bp
from users.auth import role_required


@staff_bp.route("/dashboard")
@role_required("staff")
def dashboard():
    return render_template("staff/dashboard.html")


@staff_bp.route("/orders")
@role_required("staff")
def orders():
    return render_template("staff/orders.html")







