#Registration, login, logout, and simple role checks

import re
from functools import wraps

import pymysql
from flask import flash, redirect, render_template, request, session, url_for           # these are used by the login and registration routes
from werkzeug.security import check_password_hash, generate_password_hash               

from users import auth_bp
from users.db import get_db             # provides a connection to the database

# 3 to 30 letters, numbers, dots or underscores
USERNAME_PATTERN = re.compile(r"^[a-z0-9._]{3,30}$")


@auth_bp.route("/register", methods=("GET", "POST"))
def register():
    """Create a customer account from the registration form."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not username or not email or not password:
            flash("Please fill in every field.", "error")
        elif len(name) < 2 or len(name) > 100:
            flash("Enter your full name (2 to 100 characters).", "error")
        elif not USERNAME_PATTERN.match(username):
            flash("Username must be 3 to 30 letters, numbers, dots or underscores.", "error")
        elif "@" not in email:
            flash("Enter a valid email address.", "error")
        elif len(password) < 8:
            flash("Your password must be at least 8 characters long.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        else:
            database = get_db()
            with database.cursor() as cursor:
                cursor.execute(
                    "SELECT email, username FROM users WHERE email = %s OR username = %s",
                    (email, username),
                )
                existing_users = cursor.fetchall()

            if any(row["email"] == email for row in existing_users):
                flash("An account with that email already exists.", "error")
            elif any(row["username"] == username for row in existing_users):
                flash("That username is already taken. Try another one.", "error")
            else:
                try:
                    with database.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO users (name, username, email, password_hash, role) "
                            "VALUES (%s, %s, %s, %s, 'customer')",
                            (name, username, email, generate_password_hash(password)),
                        )
                    database.commit()
                except pymysql.err.IntegrityError:
                    # Someone registered the same email or username a moment ago.
                    database.rollback()
                    flash("That email or username was just taken. Try another one.", "error")
                else:
                    flash("Your account is ready. You can log in now.", "success")
                    return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    """Check the submitted username or email and the password, then start a session."""
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")

        with get_db().cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE email = %s OR username = %s LIMIT 1",
                (identifier, identifier),
            )
            user = cursor.fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Username, email or password is incorrect.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]
            flash("Welcome back!", "success")

            if user["role"] == "admin":
                return redirect(url_for("admin.dashboard"))
            if user["role"] == "staff":
                return redirect(url_for("staff.dashboard"))
            return redirect(url_for("user.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout", methods=("POST",))
def logout():
    """End the current login session."""
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


def role_required(required_role):
    """Protect a page so only a logged-in user with this role can open it."""
    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))
            if session.get("user_role") != required_role:
                flash("You do not have permission to view that page.", "error")
                return redirect(url_for("index"))
            return view_function(*args, **kwargs)
        return wrapped_view
    return decorator
