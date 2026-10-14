"""The shop side: order queue, payments at the counter, services, inventory and sales."""
import csv
import io
from datetime import datetime, timedelta

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template,
                   request, url_for)

from app import catalog
from app.db import db
from app.models import InventoryItem, Order, SalesReport, Service, Transaction
from app.notifications import notify_customer_of_status
from app.security import roles_required
from app.utils import Pagination, current_page, parse_date, today_local
from app.validators import FormValidator

bp = Blueprint("shop", __name__, url_prefix="/shop")


def _shop():
    """The shop that the logged-in owner works for."""
    if g.user.shop is None:
        abort(403)
    return g.user.shop


def _order_or_404(order_id: int) -> Order:
    order = Order.get(order_id)
    if order is None or order.shop_id != _shop().id:
        abort(404)
    return order


def _date_range():
    """Read ?from=&to= (default: this month so far). Returns (from_date, to_date, start_dt, end_dt)."""
    today = today_local()
    first = parse_date(request.args.get("from")) or today.replace(day=1)
    last = parse_date(request.args.get("to")) or today
    if last < first:
        first, last = last, first
    start = datetime(first.year, first.month, first.day)
    end = datetime(last.year, last.month, last.day) + timedelta(days=1)
    return first, last, start, end


# ----- dashboard ------------------------------------------------------------------
@bp.route("/")
@roles_required("shop_owner")
def dashboard():
    shop = _shop()
    counts = Order.counts_by_status(shop_id=shop.id)
    waiting, _ = Order.search(shop_id=shop.id, status="pending", limit=6)
    in_progress = Order.search(shop_id=shop.id, status="accepted", limit=6)[0] + \
        Order.search(shop_id=shop.id, status="printing", limit=6)[0]
    ready, _ = Order.search(shop_id=shop.id, status="ready", limit=6)
    today = today_local()
    start, end = datetime(today.year, today.month, today.day), datetime(today.year, today.month, today.day) + timedelta(days=1)
    today_sales = SalesReport(shop.id, start, end)
    recent_payments, _, _ = Transaction.search(shop.id, limit=5)
    return render_template("shop/dashboard.html", shop=shop, counts=counts, waiting=waiting,
                           in_progress=in_progress, ready=ready, today_sales=today_sales,
                           recent_payments=recent_payments, low_stock=InventoryItem.low_stock_for(shop.id))


# ----- orders -------------------------------------------------------------------------
@bp.route("/orders")
@roles_required("shop_owner")
def orders():
    shop = _shop()
    status = request.args.get("status", "open")
    q = (request.args.get("q") or "").strip()[:60]
    first, last = parse_date(request.args.get("from")), parse_date(request.args.get("to"))
    start = datetime(first.year, first.month, first.day) if first else None
    end = datetime(last.year, last.month, last.day) + timedelta(days=1) if last else None
    kwargs = dict(shop_id=shop.id, status=status or None, q=q or None, start=start, end=end)
    total = Order.search(limit=1, **kwargs)[1]
    pager = Pagination(total, current_app.config["PER_PAGE"], current_page())
    rows, _ = Order.search(limit=pager.per_page, offset=pager.offset, **kwargs)
    return render_template("shop/orders.html", orders=rows, pager=pager, status=status, q=q,
                           date_from=first, date_to=last, counts=Order.counts_by_status(shop_id=shop.id))


@bp.route("/orders/<int:order_id>")
@roles_required("shop_owner")
def order_detail(order_id):
    order = _order_or_404(order_id)
    order.customer_name = order.customer.full_name
    return render_template("shop/order_detail.html", order=order, customer=order.customer,
                           history=order.history(), payment=order.transaction, errors={}, form={})


@bp.route("/orders/<int:order_id>/status", methods=["POST"])
@roles_required("shop_owner")
def update_status(order_id):
    order = _order_or_404(order_id)
    new_status = request.form.get("status", "")
    note = (request.form.get("note") or "").strip()[:255]
    if new_status == "rejected" and not note:
        flash("Write a short reason so the customer knows why the order was declined.", "warning")
        return redirect(url_for("shop.order_detail", order_id=order.id))
    try:
        order.change_status(new_status, g.user.id, note or None)
    except ValueError as error:
        flash(str(error), "warning")
        return redirect(url_for("shop.order_detail", order_id=order.id))
    notify_customer_of_status(order, order.customer, _shop().name)
    flash(f"Order {order.order_no} is now {order.status_label.lower()}.", "success")
    return redirect(url_for("shop.order_detail", order_id=order.id))


@bp.route("/orders/<int:order_id>/pay", methods=["POST"])
@roles_required("shop_owner")
def record_payment(order_id):
    order = _order_or_404(order_id)
    v = FormValidator(request.form)
    amount = v.amount("amount", "Amount received")
    method = v.text("method", "Payment method", choices=catalog.PAYMENT_METHODS.keys())
    note = v.text("note", "Note", required=False, max_length=255)
    if not v.is_valid:
        order.customer_name = order.customer.full_name
        return render_template("shop/order_detail.html", order=order, customer=order.customer,
                               history=order.history(), payment=order.transaction,
                               errors=v.errors, form=request.form)
    try:
        payment = order.complete_with_payment(amount, method, g.user.id, note or None)
    except ValueError as error:
        flash(str(error), "warning")
        return redirect(url_for("shop.order_detail", order_id=order.id))
    notify_customer_of_status(order, order.customer, _shop().name)
    flash(f"Payment recorded. Receipt {payment.receipt_no}.", "success")
    return redirect(url_for("shop.order_detail", order_id=order.id))


# ----- services ---------------------------------------------------------------------------
def _read_service_form(form):
    v = FormValidator(form)
    v.text("name", "Service name", min_length=2, max_length=80)
    v.text("description", "Description", required=False, max_length=255)
    sizes = [s for s in form.getlist("paper_sizes") if s in catalog.PAPER_SIZES]
    types = [t for t in form.getlist("paper_types") if t in catalog.PAPER_TYPES]
    colors = [c for c in form.getlist("color_modes") if c in catalog.COLOR_MODES]
    if not sizes:
        v.fail("paper_sizes", "Choose at least one paper size.")
    if not types:
        v.fail("paper_types", "Choose at least one paper type.")
    if not colors:
        v.fail("color_modes", "Choose at least one color option.")
    v.checkbox("is_active")
    return v, sizes, types, colors


def _service_or_404(service_id: int) -> Service:
    service = Service.get(service_id)
    if service is None or service.shop_id != _shop().id:
        abort(404)
    return service


@bp.route("/services")
@roles_required("shop_owner")
def services():
    return render_template("shop/services.html", services=_shop().services())


@bp.route("/services/new", methods=["GET", "POST"])
@roles_required("shop_owner")
def new_service():
    errors, form = {}, {"is_active": "1", "sizes": [], "types": [], "colors": ["bw", "color"]}
    if request.method == "POST":
        v, sizes, types, colors = _read_service_form(request.form)
        if v.is_valid:
            Service(shop_id=_shop().id, name=v.values["name"], description=v.values["description"] or None,
                    paper_sizes=",".join(sizes), paper_types=",".join(types), color_modes=",".join(colors),
                    is_active=v.values["is_active"]).save()
            flash("Service added.", "success")
            return redirect(url_for("shop.services"))
        errors = v.errors
        form = {**request.form.to_dict(), "sizes": sizes, "types": types, "colors": colors}
    return render_template("shop/service_form.html", service=None, errors=errors, form=form)


@bp.route("/services/<int:service_id>/edit", methods=["GET", "POST"])
@roles_required("shop_owner")
def edit_service(service_id):
    service = _service_or_404(service_id)
    errors = {}
    form = {"name": service.name, "description": service.description or "", "is_active": "1" if service.is_active else "",
            "sizes": service.size_options, "types": service.type_options, "colors": service.color_options}
    if request.method == "POST":
        v, sizes, types, colors = _read_service_form(request.form)
        if v.is_valid:
            service.name, service.description = v.values["name"], v.values["description"] or None
            service.paper_sizes, service.paper_types = ",".join(sizes), ",".join(types)
            service.color_modes, service.is_active = ",".join(colors), v.values["is_active"]
            service.save()
            flash("Service saved.", "success")
            return redirect(url_for("shop.services"))
        errors = v.errors
        form = {**request.form.to_dict(), "sizes": sizes, "types": types, "colors": colors}
    return render_template("shop/service_form.html", service=service, errors=errors, form=form)


@bp.route("/services/<int:service_id>/delete", methods=["POST"])
@roles_required("shop_owner")
def delete_service(service_id):
    service = _service_or_404(service_id)
    service.delete()
    flash("Service deleted. Past orders keep its name.", "info")
    return redirect(url_for("shop.services"))


# ----- inventory ------------------------------------------------------------------------------
def _item_or_404(item_id: int) -> InventoryItem:
    item = InventoryItem.get(item_id)
    if item is None or item.shop_id != _shop().id:
        abort(404)
    return item


@bp.route("/inventory")
@roles_required("shop_owner")
def inventory():
    category = request.args.get("category", "")
    conditions = {"shop_id": _shop().id}
    if category in catalog.INVENTORY_CATEGORIES:
        conditions["category"] = category
    items = InventoryItem.filter(order_by="name ASC", **conditions)
    return render_template("shop/inventory.html", items=items, category=category,
                           low_count=sum(1 for i in items if i.is_low))


def _read_item_form(form):
    v = FormValidator(form)
    v.text("name", "Item name", min_length=2, max_length=100)
    v.text("category", "Category", choices=catalog.INVENTORY_CATEGORIES.keys())
    v.text("unit", "Unit", choices=catalog.INVENTORY_UNITS)
    v.integer("quantity", "Quantity", minimum=0, maximum=10_000_000)
    v.integer("low_stock_level", "Low stock level", minimum=0, maximum=10_000_000)
    v.text("notes", "Notes", required=False, max_length=255)
    return v


@bp.route("/inventory/new", methods=["GET", "POST"])
@roles_required("shop_owner")
def new_item():
    errors, form = {}, {"category": "paper", "unit": "sheets", "quantity": "0", "low_stock_level": "0"}
    if request.method == "POST":
        v = _read_item_form(request.form)
        if v.is_valid:
            item = InventoryItem(shop_id=_shop().id, name=v.values["name"], category=v.values["category"],
                                 unit=v.values["unit"], quantity=0, low_stock_level=v.values["low_stock_level"],
                                 notes=v.values["notes"] or None).save()
            if v.values["quantity"]:
                item.adjust(v.values["quantity"], "Starting stock", g.user.id)
            flash("Item added.", "success")
            return redirect(url_for("shop.inventory_detail", item_id=item.id))
        errors, form = v.errors, request.form
    return render_template("shop/item_form.html", item=None, errors=errors, form=form)


@bp.route("/inventory/<int:item_id>")
@roles_required("shop_owner")
def inventory_detail(item_id):
    item = _item_or_404(item_id)
    return render_template("shop/item_detail.html", item=item, logs=item.logs(), errors={}, form={})


@bp.route("/inventory/<int:item_id>/edit", methods=["GET", "POST"])
@roles_required("shop_owner")
def edit_item(item_id):
    item = _item_or_404(item_id)
    errors = {}
    form = {"name": item.name, "category": item.category, "unit": item.unit,
            "quantity": item.quantity, "low_stock_level": item.low_stock_level, "notes": item.notes or ""}
    if request.method == "POST":
        v = _read_item_form(request.form)
        if v.is_valid:
            old_quantity = item.quantity
            item.name, item.category, item.unit = v.values["name"], v.values["category"], v.values["unit"]
            item.low_stock_level, item.notes = v.values["low_stock_level"], v.values["notes"] or None
            item.save()
            if v.values["quantity"] != old_quantity:
                item.adjust(v.values["quantity"] - old_quantity, "Corrected on edit", g.user.id)
            flash("Item saved.", "success")
            return redirect(url_for("shop.inventory_detail", item_id=item.id))
        errors, form = v.errors, request.form
    return render_template("shop/item_form.html", item=item, errors=errors, form=form)


@bp.route("/inventory/<int:item_id>/adjust", methods=["POST"])
@roles_required("shop_owner")
def adjust_item(item_id):
    item = _item_or_404(item_id)
    v = FormValidator(request.form)
    direction = v.text("direction", "Action", choices=("add", "remove"))
    amount = v.integer("amount", "Amount", minimum=1, maximum=10_000_000)
    reason = v.text("reason", "Reason", required=False, max_length=120)
    if v.is_valid:
        try:
            item.adjust(amount if direction == "add" else -amount,
                        reason or ("Stock added" if direction == "add" else "Stock used"), g.user.id)
        except ValueError as error:
            v.fail("amount", str(error))
    if not v.is_valid:
        return render_template("shop/item_detail.html", item=item, logs=item.logs(),
                               errors=v.errors, form=request.form)
    flash(f"Stock updated. {item.name}: {item.quantity} {item.unit}.", "success")
    return redirect(url_for("shop.inventory_detail", item_id=item.id))


@bp.route("/inventory/<int:item_id>/delete", methods=["POST"])
@roles_required("shop_owner")
def delete_item(item_id):
    _item_or_404(item_id).delete()
    flash("Item deleted.", "info")
    return redirect(url_for("shop.inventory"))


# ----- sales and transactions ----------------------------------------------------------------------
@bp.route("/sales")
@roles_required("shop_owner")
def sales():
    shop = _shop()
    first, last, start, end = _date_range()
    method = request.args.get("method", "")
    report = SalesReport(shop.id, start, end)
    total = Transaction.search(shop.id, start, end, method, limit=1)[1]
    pager = Pagination(total, current_app.config["PER_PAGE"], current_page())
    rows, _, filtered_amount = Transaction.search(shop.id, start, end, method,
                                                  limit=pager.per_page, offset=pager.offset)
    days = report.by_day()
    biggest = max((d["total"] for d in days), default=0) or 1
    return render_template("shop/sales.html", report=report, days=days, biggest=biggest, rows=rows,
                           pager=pager, date_from=first, date_to=last, method=method,
                           filtered_amount=filtered_amount)


def _csv_safe(value) -> str:
    """Stop spreadsheet programs from running text such as =HYPERLINK(...) as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@bp.route("/sales/export.csv")
@roles_required("shop_owner")
def export_sales():
    first, last, start, end = _date_range()
    rows, _, _ = Transaction.search(_shop().id, start, end, request.args.get("method", ""))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Receipt", "Date", "Order", "Customer", "Method", "Amount", "Note"])
    for t in rows:
        writer.writerow([t.receipt_no, t.created_at.strftime("%Y-%m-%d %H:%M"), t.order_no,
                         _csv_safe(t.customer_name), t.method_label, f"{float(t.amount):.2f}", _csv_safe(t.note)])
    return Response(buffer.getvalue(), mimetype="text/csv", headers={
        "Content-Disposition": f"attachment; filename=printwise-sales-{first}-to-{last}.csv"})


# ----- shop details ----------------------------------------------------------------------------------
@bp.route("/settings", methods=["GET", "POST"])
@roles_required("shop_owner")
def settings():
    shop = _shop()
    errors = {}
    form = {"name": shop.name, "address": shop.address, "contact_phone": shop.contact_phone or "",
            "contact_email": shop.contact_email or "", "hours": shop.hours or "",
            "description": shop.description or "", "accepting_orders": "1" if shop.accepting_orders else ""}
    if request.method == "POST":
        v = FormValidator(request.form)
        v.text("name", "Shop name", min_length=2, max_length=120)
        v.text("address", "Address", min_length=5, max_length=255)
        v.phone("contact_phone", "Shop phone")
        v.email("contact_email", "Shop email", required=False)
        v.text("hours", "Opening hours", required=False, max_length=160)
        v.text("description", "About the shop", required=False, max_length=1000)
        v.checkbox("accepting_orders")
        if v.is_valid:
            shop.name, shop.address = v.values["name"], v.values["address"]
            shop.contact_phone = v.values["contact_phone"] or None
            shop.contact_email = v.values["contact_email"] or None
            shop.hours, shop.description = v.values["hours"] or None, v.values["description"] or None
            shop.accepting_orders = v.values["accepting_orders"]
            shop.save()
            flash("Shop details saved.", "success")
            return redirect(url_for("shop.settings"))
        errors, form = v.errors, request.form
    return render_template("shop/settings.html", shop=shop, errors=errors, form=form)
