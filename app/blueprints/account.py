"""Things every logged-in user can do: manage their profile and read notifications."""
from flask import (Blueprint, abort, flash, g, redirect, render_template, request,
                   send_file, url_for)

from app.models import Notification, User
from app.notifications import send_verification_email
from app.security import login_required
from app.uploads import FileStore
from app.validators import FormValidator

bp = Blueprint("account", __name__)


def _render_profile(errors=None, form=None, open_form="details"):
    values = form if form is not None else {
        "full_name": g.user.full_name, "username": g.user.username,
        "email": g.user.email, "phone": g.user.phone or "",
    }
    return render_template("account/profile.html", form=values, errors=errors or {}, open_form=open_form)


@bp.route("/profile")
@login_required
def profile():
    return _render_profile()


@bp.route("/profile/details", methods=["POST"])
@login_required
def update_details():
    v = FormValidator(request.form)
    full_name = v.text("full_name", "Full name", min_length=2, max_length=120)
    username = v.username("username")
    email = v.email("email")
    phone = v.phone("phone")
    if username and User.username_taken(username, except_id=g.user.id):
        v.fail("username", "That username is already taken. Try another one.")
    if email and User.email_taken(email, except_id=g.user.id):
        v.fail("email", "Another account already uses this email.")
    if not v.is_valid:
        return _render_profile(v.errors, request.form, "details")
    email_changed = email != g.user.email
    g.user.full_name, g.user.username, g.user.email = full_name, username, email
    g.user.phone = phone or None
    if email_changed:
        g.user.email_verified = 0
    g.user.save()
    if email_changed:
        send_verification_email(g.user)
        flash("Details saved. We sent a link to confirm your new email address.", "success")
    else:
        flash("Your details are saved.", "success")
    return redirect(url_for("account.profile"))


@bp.route("/profile/password", methods=["POST"])
@login_required
def change_password():
    v = FormValidator(request.form)
    if not g.user.check_password(request.form.get("current_password") or ""):
        v.fail("current_password", "That is not your current password.")
    password = v.password("password", "New password")
    if password:
        v.same("confirm_password", "password", "The two passwords do not match.")
        if g.user.check_password(password):
            v.fail("password", "Choose a password different from the current one.")
    if not v.is_valid:
        return _render_profile(v.errors, None, "password")
    g.user.set_password(password)
    g.user.save()
    flash("Your password is changed.", "success")
    return redirect(url_for("account.profile"))


@bp.route("/profile/photo", methods=["POST"])
@login_required
def upload_photo():
    try:
        stored = FileStore.save_avatar(request.files.get("photo"))
    except ValueError as error:
        return _render_profile({"photo": str(error)}, None, "photo")
    FileStore.delete_avatar(g.user.avatar_filename)
    g.user.avatar_filename = stored
    g.user.save()
    flash("Your profile photo is updated.", "success")
    return redirect(url_for("account.profile"))


@bp.route("/profile/photo/remove", methods=["POST"])
@login_required
def remove_photo():
    FileStore.delete_avatar(g.user.avatar_filename)
    g.user.avatar_filename = None
    g.user.save()
    flash("Your profile photo is removed.", "info")
    return redirect(url_for("account.profile"))


@bp.route("/media/avatar/<filename>")
@login_required
def avatar(filename):
    path = FileStore.avatar_path(filename)
    if not path.is_file():
        abort(404)
    response = send_file(path)
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response


@bp.route("/notifications")
@login_required
def notifications():
    items = Notification.for_user(g.user.id)
    unread_ids = {n.id for n in items if not n.is_read}
    if unread_ids:
        Notification.mark_all_read(g.user.id)
    return render_template("account/notifications.html", items=items, unread_ids=unread_ids)


@bp.route("/orders/<int:order_id>/file")
@login_required
def order_file(order_id):
    """Download the file of an order. Only the customer who sent it and that shop's staff may open it."""
    from app.models import Order
    order = Order.get(order_id)
    if order is None:
        abort(404)
    allowed = (g.user.is_customer and order.customer_id == g.user.id) or \
              (g.user.is_shop_owner and g.user.shop_id == order.shop_id)
    if not allowed:
        abort(403)
    path = FileStore.order_file_path(order.file_stored)
    if not path.is_file():
        flash("The file for this order is no longer available.", "danger")
        return redirect(url_for(g.user.home_endpoint()))
    return send_file(path, as_attachment=True, download_name=order.file_name)
