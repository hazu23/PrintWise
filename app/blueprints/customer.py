"""The customer side: send print jobs to a shop and follow them until pickup."""
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from app import catalog
from app.db import db
from app.models import Order, PrintShop, Service
from app.notifications import notify, notify_shop_of_new_order
from app.security import roles_required
from app.uploads import FileStore
from app.utils import Pagination, current_page
from app.validators import FormValidator

bp = Blueprint("customer", __name__, url_prefix="/customer")


def _own_order_or_404(order_id: int) -> Order:
    order = Order.get(order_id)
    if order is None or order.customer_id != g.user.id:
        abort(404)
    return order


@bp.route("/")
@roles_required("customer")
def dashboard():
    counts = Order.counts_by_status(customer_id=g.user.id)
    open_orders, _ = Order.search(customer_id=g.user.id, status="open", limit=5)
    recent, _ = Order.search(customer_id=g.user.id, limit=5)
    shops = [s for s in PrintShop.filter(order_by="name ASC", is_active=1) if s.can_receive_orders]
    return render_template("customer/dashboard.html", counts=counts, open_orders=open_orders,
                           recent=recent, shops=shops,
                           open_total=sum(counts[s] for s in Order.OPEN_STATUSES))


@bp.route("/orders")
@roles_required("customer")
def orders():
    status = request.args.get("status", "")
    q = (request.args.get("q") or "").strip()[:60]
    total = Order.search(customer_id=g.user.id, status=status or None, q=q or None, limit=1)[1]
    pager = Pagination(total, current_app.config["PER_PAGE"], current_page())
    rows, _ = Order.search(customer_id=g.user.id, status=status or None, q=q or None,
                           limit=pager.per_page, offset=pager.offset)
    return render_template("customer/orders.html", orders=rows, pager=pager, status=status, q=q)


# ----- creating and editing an order -----------------------------------------------
def _read_order_form(shop: PrintShop, form, files, require_file: bool):
    """Validate the order form. Returns (validator, service, spec, file_info)."""
    v = FormValidator(form)
    service = None
    service_id = v.integer("service_id", "Service", minimum=1)
    if service_id:
        service = Service.find_by(id=service_id, shop_id=shop.id)
        if service is None or not service.is_active:
            service = None
            v.fail("service_id", "Choose one of the services this shop offers.")

    size = v.text("paper_size", "Paper size", choices=catalog.PAPER_SIZES)
    ptype = v.text("paper_type", "Paper type", choices=catalog.PAPER_TYPES)
    color = v.text("color_mode", "Color", choices=catalog.COLOR_MODES.keys())
    v.text("sides", "Printing sides", choices=catalog.SIDES.keys())
    copies = v.integer("copies", "Copies", minimum=1, maximum=500)
    pages = v.integer("pages", "Number of pages", minimum=1, maximum=5000, required=False)
    notes = v.text("notes", "Notes", required=False, max_length=500)

    if size == catalog.CUSTOM_SIZE:
        detail = v.text("custom_size", "Custom size", max_length=60)
        size = f"Custom: {detail}" if detail else None
    if ptype == catalog.OTHER_TYPE:
        detail = v.text("custom_type", "Paper type details", max_length=60)
        ptype = f"Other: {detail}" if detail else None

    if service:
        raw_size, raw_type = form.get("paper_size", ""), form.get("paper_type", "")
        if raw_size in catalog.PAPER_SIZES and raw_size not in service.size_options:
            v.fail("paper_size", "This shop does not offer that size for this service.")
        if raw_type in catalog.PAPER_TYPES and raw_type not in service.type_options:
            v.fail("paper_type", "This shop does not offer that paper type for this service.")
        if color and color not in service.color_options:
            v.fail("color_mode", "This shop does not offer that color option for this service.")

    file_info = None
    upload = files.get("file")
    if upload is not None and upload.filename:
        if v.is_valid:  # do not store a file for a form that is going to be rejected anyway
            try:
                file_info = FileStore.save_order_file(upload)
            except ValueError as error:
                v.fail("file", str(error))
    elif require_file:
        v.fail("file", "Attach the file you want printed.")

    spec = {"paper_size": size, "paper_type": ptype, "color_mode": color,
            "sides": v.values.get("sides"), "copies": copies, "pages": pages, "notes": notes or None}
    return v, service, spec, file_info


def _order_form_context(shop, errors, form, order=None):
    services = shop.services(only_active=True)
    return dict(shop=shop, services=services, errors=errors, form=form, order=order,
                options={s.id: s.to_option_dict() for s in services})


@bp.route("/orders/new", methods=["GET", "POST"])
@roles_required("customer")
def new_order():
    if current_app.config["REQUIRE_VERIFIED_EMAIL_TO_ORDER"] and not g.user.email_verified:
        flash("Confirm your email address before placing an order. Check your inbox for the link.", "warning")
        return redirect(url_for("customer.dashboard"))

    shop_id = request.values.get("shop", type=int)
    shop = PrintShop.get(shop_id) if shop_id else None
    if shop is None or not shop.is_active:
        shops = [s for s in PrintShop.filter(order_by="name ASC", is_active=1)]
        return render_template("customer/choose_shop.html", shops=shops)
    if not shop.can_receive_orders:
        flash(f"{shop.name} is not taking new orders right now. Choose another shop.", "warning")
        return redirect(url_for("customer.new_order"))

    if request.method == "POST":
        v, service, spec, file_info = _read_order_form(shop, request.form, request.files, require_file=True)
        if v.is_valid:
            stored_name, display_name, size = file_info[1], file_info[0], file_info[2]
            order = Order(customer_id=g.user.id, shop_id=shop.id, service_id=service.id,
                          service_name=service.name, file_name=display_name,
                          file_stored=stored_name, file_size=size, **spec)
            try:
                order.place(g.user.id)
            except Exception:
                FileStore.delete_order_file(stored_name)
                raise
            order.customer_name = g.user.full_name
            notify_shop_of_new_order(order, shop.owners())
            flash(f"Order {order.order_no} sent to {shop.name}. You will see its status here.", "success")
            return redirect(url_for("customer.order_detail", order_id=order.id))
        return render_template("customer/order_form.html", **_order_form_context(shop, v.errors, request.form))
    return render_template("customer/order_form.html", **_order_form_context(shop, {}, {"copies": "1", "sides": "single"}))


@bp.route("/orders/<int:order_id>")
@roles_required("customer")
def order_detail(order_id):
    order = _own_order_or_404(order_id)
    return render_template("customer/order_detail.html", order=order, shop=order.shop, history=order.history())


def _form_from_order(order: Order) -> dict:
    form = {"service_id": order.service_id, "paper_size": order.paper_size, "paper_type": order.paper_type,
            "color_mode": order.color_mode, "sides": order.sides, "copies": order.copies,
            "pages": order.pages or "", "notes": order.notes or ""}
    if order.paper_size.startswith("Custom: "):
        form["paper_size"], form["custom_size"] = catalog.CUSTOM_SIZE, order.paper_size[len("Custom: "):]
    if order.paper_type.startswith("Other: "):
        form["paper_type"], form["custom_type"] = catalog.OTHER_TYPE, order.paper_type[len("Other: "):]
    return form


@bp.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
@roles_required("customer")
def edit_order(order_id):
    order = _own_order_or_404(order_id)
    if not order.customer_can_edit:
        flash("This order can no longer be changed because the shop already started on it.", "warning")
        return redirect(url_for("customer.order_detail", order_id=order.id))
    shop = order.shop
    if request.method == "POST":
        v, service, spec, file_info = _read_order_form(shop, request.form, request.files, require_file=False)
        if v.is_valid:
            old_file = None
            if file_info:
                old_file = order.file_stored
                order.file_name, order.file_stored, order.file_size = file_info
            order.service_id, order.service_name = service.id, service.name
            for key, value in spec.items():
                setattr(order, key, value)
            order.save()
            FileStore.delete_order_file(old_file)
            for owner in shop.owners():
                notify(owner, "Order changed", f"{order.order_no} was updated by the customer.",
                       url_for("shop.order_detail", order_id=order.id))
            flash("Your changes are saved.", "success")
            return redirect(url_for("customer.order_detail", order_id=order.id))
        return render_template("customer/order_form.html", **_order_form_context(shop, v.errors, request.form, order))
    return render_template("customer/order_form.html", **_order_form_context(shop, {}, _form_from_order(order), order))


@bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@roles_required("customer")
def cancel_order(order_id):
    order = _own_order_or_404(order_id)
    try:
        order.cancel(g.user.id)
    except ValueError as error:
        flash(str(error), "warning")
    else:
        for owner in order.shop.owners():
            notify(owner, "Order cancelled", f"{order.order_no} was cancelled by the customer.",
                   url_for("shop.order_detail", order_id=order.id))
        flash(f"Order {order.order_no} is cancelled.", "info")
    return redirect(url_for("customer.order_detail", order_id=order.id))


@bp.route("/orders/<int:order_id>/delete", methods=["POST"])
@roles_required("customer")
def delete_order(order_id):
    order = _own_order_or_404(order_id)
    if not order.customer_can_delete:
        flash("Only cancelled or declined orders can be deleted.", "warning")
        return redirect(url_for("customer.order_detail", order_id=order.id))
    FileStore.delete_order_file(order.file_stored)
    order.delete()
    flash("The order is deleted.", "info")
    return redirect(url_for("customer.orders"))
