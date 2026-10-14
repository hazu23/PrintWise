"""Registration, login, logout, email confirmation and password reset."""
from flask import Blueprint, flash, g, redirect, render_template, request, current_app, url_for

from app.models import Customer, User
from app.notifications import (RESET_MAX_AGE, VERIFY_MAX_AGE, send_password_reset_email,
                               send_verification_email)
from app.security import (login_required, login_user, logout_user, read_token, safe_next_url)
from app.validators import FormValidator

bp = Blueprint("auth", __name__)

LOGIN_ERROR = "That username or password is not right. Check both and try again."


def _home():
    return url_for(g.user.home_endpoint())


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(_home())
    errors = {}
    if request.method == "POST":
        v = FormValidator(request.form)
        full_name = v.text("full_name", "Full name", min_length=2, max_length=120)
        username = v.username("username")
        email = v.email("email")
        phone = v.phone("phone")
        password = v.password("password")
        if password:
            v.same("confirm_password", "password", "The two passwords do not match.")
        if username and User.username_taken(username):
            v.fail("username", "That username is already taken. Try another one.")
        if email and User.email_taken(email):
            v.fail("email", "An account with this email already exists. Log in instead.")
        if v.is_valid:
            user = Customer(full_name=full_name, username=username, email=email, phone=phone or None)
            user.set_password(password)
            user.save()
            send_verification_email(user)
            login_user(user)
            flash(f"Welcome to PrintWise, {user.first_name}. We sent a confirmation link to {user.email}.", "success")
            return redirect(url_for("customer.dashboard"))
        errors = v.errors
    return render_template("auth/register.html", form=request.form, errors=errors)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(_home())
    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""
        user = User.find_by_login(identifier) if identifier else None
        config = current_app.config
        if user and user.is_locked():
            flash(f"Too many wrong attempts. Try again in {user.minutes_until_unlock()} minutes, "
                  "or reset your password.", "danger")
        elif user and user.check_password(password):
            if not user.is_active:
                flash("This account has been turned off. Contact the PrintWise administrator.", "danger")
            else:
                user.register_successful_login()
                login_user(user)
                flash(f"Welcome back, {user.first_name}.", "success")
                return redirect(safe_next_url(request.args.get("next"), url_for(user.home_endpoint())))
        else:
            if user:
                user.register_failed_login(config["MAX_FAILED_LOGINS"], config["LOCKOUT_MINUTES"])
            flash(LOGIN_ERROR, "danger")
    return render_template("auth/login.html", form=request.form)


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You are logged out.", "info")
    return redirect(url_for("public.index"))


@bp.route("/verify/<token>")
def verify_email(token):
    data = read_token("verify", token, VERIFY_MAX_AGE)
    user = User.get(data["uid"]) if data else None
    if user is None or user.email != data["email"]:
        flash("That confirmation link is not valid or has expired. Log in and ask for a new one.", "danger")
        return redirect(url_for("auth.login"))
    user.email_verified = 1
    user.save()
    flash("Your email address is confirmed.", "success")
    return redirect(url_for(user.home_endpoint()) if g.user else url_for("auth.login"))


@bp.route("/verify/resend", methods=["POST"])
@login_required
def resend_verification():
    if g.user.email_verified:
        flash("Your email is already confirmed.", "info")
    else:
        send_verification_email(g.user)
        flash(f"We sent a new confirmation link to {g.user.email}.", "success")
    return redirect(request.referrer if request.referrer and request.referrer.startswith(request.host_url)
                    else url_for(g.user.home_endpoint()))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    errors = {}
    if request.method == "POST":
        v = FormValidator(request.form)
        email = v.email("email")
        if v.is_valid:
            user = User.find_by_login(email)
            if user and user.is_active:
                send_password_reset_email(user)
            # The same message either way, so nobody can test which emails have accounts.
            flash("If that email belongs to an account, a reset link is on its way. It works for 1 hour.", "info")
            return redirect(url_for("auth.login"))
        errors = v.errors
    return render_template("auth/forgot.html", form=request.form, errors=errors)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    data = read_token("reset", token, RESET_MAX_AGE)
    user = User.get(data["uid"]) if data else None
    if user is None or (user.password_hash or "")[-12:] != data["ph"]:
        flash("That reset link is not valid, has expired, or was already used. Ask for a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))
    errors = {}
    if request.method == "POST":
        v = FormValidator(request.form)
        password = v.password("password", "New password")
        if password:
            v.same("confirm_password", "password", "The two passwords do not match.")
        if v.is_valid:
            user.set_password(password)
            user.must_change_password = 0
            user.failed_logins, user.locked_until = 0, None
            user.save()
            flash("Your password is changed. Log in with the new one.", "success")
            return redirect(url_for("auth.login"))
        errors = v.errors
    return render_template("auth/reset.html", form=request.form, errors=errors, token=token)


@bp.route("/welcome/setup", methods=["GET", "POST"])
@login_required
def first_login_setup():
    """First login for accounts created by the administrator: choose your own username and password."""
    if not g.user.must_change_password:
        return redirect(_home())
    errors = {}
    if request.method == "POST":
        v = FormValidator(request.form)
        username = v.username("username", "New username")
        password = v.password("password", "New password")
        if password:
            v.same("confirm_password", "password", "The two passwords do not match.")
        if username and User.username_taken(username, except_id=g.user.id):
            v.fail("username", "That username is already taken. Try another one.")
        if password and g.user.check_password(password):
            v.fail("password", "Choose a password different from the temporary one.")
        if v.is_valid:
            g.user.username = username
            g.user.set_password(password)
            g.user.must_change_password = 0
            g.user.save()
            flash("Your account is set up. Welcome to PrintWise.", "success")
            return redirect(_home())
        errors = v.errors
    form = request.form if request.method == "POST" else {"username": g.user.username}
    return render_template("auth/setup.html", form=form, errors=errors)
