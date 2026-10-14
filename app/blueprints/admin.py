"""The administrator side: register print shop clients and look after accounts."""
import secrets

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from app import catalog
from app.db import db
from app.models import Order, PrintShop, Service, ShopOwner, User
from app.notifications import send_shop_account_email
from app.security import roles_required
from app.utils import Pagination, current_page
from app.validators import FormValidator, password_problem

bp = Blueprint("admin", __name__, url_prefix="/admin")

SAFE_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def make_temporary_password(length: int = 10) -> str:
    """Random password that passes the password rules (letters and digits, no look-alike characters)."""
    while True:
        candidate = "".join(secrets.choice(SAFE_CHARS) for _ in range(length))
        if password_problem(candidate) is None:
            return candidate


@bp.route("/")
@roles_required("admin")
def dashboard():
    stats = {
        "shops": PrintShop.count(),
        "active_shops": PrintShop.count(is_active=1),
        "customers": User.count(role="customer"),
        "orders": Order.count(),
    }
    counts = Order.counts_by_status()
    recent_orders, _ = Order.search(limit=6)
    shops = PrintShop.filter(order_by="name ASC")
    shop_rows = [{"shop": s, "orders": s.order_count(), "owners": s.owners()} for s in shops]
    return render_template("admin/dashboard.html", stats=stats, counts=counts,
                           recent_orders=recent_orders, shop_rows=shop_rows)


# ----- print shop clients ---------------------------------------------------------------
def _shop_or_404(shop_id: int) -> PrintShop:
    shop = PrintShop.get(shop_id)
    if shop is None:
        abort(404)
    return shop


@bp.route("/shops")
@roles_required("admin")
def shops():
    rows = [{"shop": s, "orders": s.order_count(), "owners": s.owners()}
            for s in PrintShop.filter(order_by="name ASC")]
    return render_template("admin/shops.html", rows=rows)


def _read_shop_fields(v: FormValidator):
    v.text("name", "Shop name", min_length=2, max_length=120)
    v.text("address", "Address", min_length=5, max_length=255)
    v.phone("contact_phone", "Shop phone")
    v.email("contact_email", "Shop email", required=False)
    v.text("hours", "Opening hours", required=False, max_length=160)
    v.text("description", "About the shop", required=False, max_length=1000)


def _add_starter_services(shop: PrintShop) -> None:
    """Give a new shop two ready-made services so customers can order right away."""
    Service(shop_id=shop.id, name="Document printing", description="Reports, school papers, forms and receipts.",
            paper_sizes="Short (8.5 x 11 in),A4 (8.3 x 11.7 in),Long (8.5 x 13 in)",
            paper_types="Bond paper", color_modes="bw,color").save()
    Service(shop_id=shop.id, name="Photo printing", description="Photos on photo paper.",
            paper_sizes="Photo 4R (4 x 6 in),Photo 5R (5 x 7 in),Photo 8R (8 x 10 in)",
            paper_types="Glossy photo paper,Matte photo paper", color_modes="color").save()


@bp.route("/shops/new", methods=["GET", "POST"])
@roles_required("admin")
def new_shop():
    errors, form = {}, {"temporary_password": make_temporary_password()}
    if request.method == "POST":
        v = FormValidator(request.form)
        _read_shop_fields(v)
        full_name = v.text("owner_name", "Owner's full name", min_length=2, max_length=120)
        username = v.username("owner_username", "Owner's username")
        email = v.email("owner_email", "Owner's email")
        v.phone("owner_phone", "Owner's phone")
        temporary = v.password("temporary_password", "Temporary password")
        if username and User.username_taken(username):
            v.fail("owner_username", "That username is already taken.")
        if email and User.email_taken(email):
            v.fail("owner_email", "Another account already uses this email.")
        if v.is_valid:
            with db.transaction():
                shop = PrintShop(name=v.values["name"], address=v.values["address"],
                                 contact_phone=v.values["contact_phone"] or None,
                                 contact_email=v.values["contact_email"] or None,
                                 hours=v.values["hours"] or None, description=v.values["description"] or None).save()
                owner = ShopOwner(full_name=full_name, username=username, email=email,
                                  phone=v.values["owner_phone"] or None, shop_id=shop.id, must_change_password=1)
                owner.set_password(temporary)
                owner.save()
                _add_starter_services(shop)
            send_shop_account_email(owner, shop)
            return render_template("admin/credentials.html", shop=shop, user=owner, password=temporary, created=True)
        errors, form = v.errors, request.form
    return render_template("admin/shop_form.html", shop=None, errors=errors, form=form)


@bp.route("/shops/<int:shop_id>")
@roles_required("admin")
def shop_detail(shop_id):
    shop = _shop_or_404(shop_id)
    return render_template("admin/shop_detail.html", shop=shop, owners=shop.owners(),
                           services=shop.services(), counts=Order.counts_by_status(shop_id=shop.id))


@bp.route("/shops/<int:shop_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_shop(shop_id):
    shop = _shop_or_404(shop_id)
    errors = {}
    form = {"name": shop.name, "address": shop.address, "contact_phone": shop.contact_phone or "",
            "contact_email": shop.contact_email or "", "hours": shop.hours or "",
            "description": shop.description or "", "is_active": "1" if shop.is_active else ""}
    if request.method == "POST":
        v = FormValidator(request.form)
        _read_shop_fields(v)
        v.checkbox("is_active")
        if v.is_valid:
            shop.name, shop.address = v.values["name"], v.values["address"]
            shop.contact_phone = v.values["contact_phone"] or None
            shop.contact_email = v.values["contact_email"] or None
            shop.hours, shop.description = v.values["hours"] or None, v.values["description"] or None
            shop.is_active = v.values["is_active"]
            shop.save()
            flash("Shop saved.", "success")
            return redirect(url_for("admin.shop_detail", shop_id=shop.id))
        errors, form = v.errors, request.form
    return render_template("admin/shop_form.html", shop=shop, errors=errors, form=form)


@bp.route("/shops/<int:shop_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_shop(shop_id):
    shop = _shop_or_404(shop_id)
    shop.is_active = 0 if shop.is_active else 1
    shop.save()
    flash(f"{shop.name} is now {'visible to customers' if shop.is_active else 'hidden from customers'}.", "info")
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("admin.shops"))


@bp.route("/shops/<int:shop_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_shop(shop_id):
    shop = _shop_or_404(shop_id)
    if shop.has_orders():
        flash("This shop already has orders, so it cannot be deleted. Hide it from customers instead.", "warning")
        return redirect(url_for("admin.shop_detail", shop_id=shop.id))
    shop.delete_with_owners()
    flash("Shop and its owner accounts are deleted.", "info")
    return redirect(url_for("admin.shops"))


# ----- accounts ---------------------------------------------------------------------------------
def _user_or_404(user_id: int) -> User:
    user = User.get(user_id)
    if user is None:
        abort(404)
    return user


@bp.route("/users")
@roles_required("admin")
def users():
    role = request.args.get("role", "")
    q = (request.args.get("q") or "").strip()[:60]
    where, params = [], []
    if role in ("customer", "shop_owner", "admin"):
        where.append("role = %s")
        params.append(role)
    if q:
        where.append("(full_name LIKE %s OR username LIKE %s OR email LIKE %s)")
        params += [f"%{q}%"] * 3
    clause = " WHERE " + " AND ".join(where) if where else ""
    total = int(db.scalar("SELECT COUNT(*) FROM users" + clause, params))
    pager = Pagination(total, current_app.config["PER_PAGE"], current_page())
    rows = User.select("SELECT * FROM users" + clause + " ORDER BY id DESC LIMIT %s OFFSET %s",
                       params + [pager.per_page, pager.offset])
    return render_template("admin/users.html", users=rows, pager=pager, role=role, q=q)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@roles_required("admin")
def toggle_user(user_id):
    user = _user_or_404(user_id)
    if user.id == g.user.id:
        flash("You cannot turn off your own account.", "warning")
    else:
        user.is_active = 0 if user.is_active else 1
        user.save()
        flash(f"{user.full_name}'s account is now {'on' if user.is_active else 'off'}.", "info")
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for("admin.users"))


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@roles_required("admin")
def reset_user_password(user_id):
    user = _user_or_404(user_id)
    if user.id == g.user.id:
        flash("Change your own password from your profile.", "warning")
        return redirect(url_for("admin.users"))
    temporary = make_temporary_password()
    user.set_password(temporary)
    user.must_change_password = 1
    user.failed_logins, user.locked_until = 0, None
    user.save()
    return render_template("admin/credentials.html", shop=user.shop, user=user, password=temporary, created=False)


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_user(user_id):
    user = _user_or_404(user_id)
    if user.id == g.user.id:
        flash("You cannot delete your own account.", "warning")
    elif user.is_customer and Order.count(customer_id=user.id):
        flash("This customer has orders, so the account cannot be deleted. Turn it off instead.", "warning")
    else:
        user.delete()
        flash("Account deleted.", "info")
    return redirect(url_for("admin.users"))


# ----- all orders (read only) ---------------------------------------------------------------------------
@bp.route("/orders")
@roles_required("admin")
def orders():
    status = request.args.get("status", "")
    q = (request.args.get("q") or "").strip()[:60]
    shop_id = request.args.get("shop", type=int)
    total = Order.search(shop_id=shop_id, status=status or None, q=q or None, limit=1)[1]
    pager = Pagination(total, current_app.config["PER_PAGE"], current_page())
    rows, _ = Order.search(shop_id=shop_id, status=status or None, q=q or None,
                           limit=pager.per_page, offset=pager.offset)
    return render_template("admin/orders.html", orders=rows, pager=pager, status=status, q=q,
                           shop_id=shop_id, shops=PrintShop.filter(order_by="name ASC"))
