#Registration, login, logout, and simple role checks

import re
from difflib import SequenceMatcher
from functools import wraps

from flask import flash, jsonify, redirect, render_template, request, session, url_for  # these are used by the login and registration routes
from werkzeug.security import check_password_hash, generate_password_hash
from email_validator import EmailNotValidError, validate_email

from users import auth_bp
from users.db import get_db  # provides a connection to the database

COMMON_EMAIL_DOMAINS = (
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "rocketmail.com",
    "ymail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
)


def is_valid_full_name(name):
    """Allow letter-only name parts, middle initials, and common suffixes."""
    # Names must not start or end with spaces or contain repeated spaces.
    if not name or len(name) > 50 or name != name.strip() or "  " in name:
        return False

    parts = name.split(" ")
    suffixes = {"sr.", "jr.", "ii", "iii", "iv", "v", "vi"}

    # Remove a recognized suffix before checking the person's first and last names.
    if parts[-1].casefold() in suffixes:
        parts.pop()

    # A full name needs at least a first name and a last name.
    if len(parts) < 2 or not parts[0].isalpha() or not parts[-1].isalpha():
        return False

    # Require six letters in the actual name; punctuation and suffixes do not count.
    letter_count = 0
    for part in parts:
        for character in part:
            if character.isalpha():
                letter_count += 1

    if letter_count < 6:
        return False

    # Middle names may be words or a single letter followed by a period.
    for part in parts[1:-1]:
        if part.isalpha():
            continue
        if len(part) == 2 and part[0].isalpha() and part[1] == ".":
            continue
        return False

    return True


def is_valid_email(email):
    """Check email syntax and whether its domain can receive email."""
    if len(email) > 254:
        return False

    try:
        # Check the domain's mail records; this works with different email providers.
        validate_email(email, check_deliverability=True, timeout=3)
    except EmailNotValidError:
        return False

    return True


def suggest_email_address(email):
    """Suggest a common provider when its domain looks misspelled."""
    if email.count("@") != 1:
        return None

    email_name, domain = email.split("@")
    closest_domain = max(
        COMMON_EMAIL_DOMAINS,
        key=lambda provider: SequenceMatcher(None, domain, provider).ratio(),
    )
    similarity = SequenceMatcher(None, domain, closest_domain).ratio()

    # Only suggest when the typed domain is very close to a common provider.
    if domain != closest_domain and similarity >= 0.78:
        return f"{email_name}@{closest_domain}"

    return None


@auth_bp.route("/register", methods=("GET", "POST"))
def register():
    """Create a customer account from the registration form."""
    if request.method == "POST":
        name = request.form.get("name", "")
        username = request.form.get("username", "").lower()
        email = request.form.get("email", "").lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        suggested_email = suggest_email_address(email)

        if not name or not username or not email or not password:
            flash("Please fill in every field.", "error")
        elif not is_valid_full_name(name):
            flash(
                "Enter a full name with at least two words and six letters. Use letters and single spaces; a middle initial may end with a period, and suffixes like Jr., Sr., or III are allowed.",
                "error",
            )
        elif not re.fullmatch(r"[a-z0-9_.]{3,20}", username):
            flash(
                "Username must be 3–20 characters. Use letters, numbers, underscores (_), or periods (.); spaces aren't allowed.",
                "error",
            )
        elif any(character.isspace() for character in email):
            flash("Spaces aren't allowed in an email address.", "error")
        elif len(email) > 254:
            flash("Email addresses can't be longer than 254 characters.", "error")
        elif suggested_email and request.form.get("email_custom_confirmed") != "yes":
            flash(
                f"Check your email address. Did you mean {suggested_email}? Correct it or confirm the address you entered.",
                "error",
            )
        elif not is_valid_email(email):
            flash("Enter a valid email address with a domain that can receive email.", "error")
        elif any(character.isspace() for character in password) or any(
            character.isspace() for character in confirm_password
        ):
            flash("Spaces aren't allowed in passwords.", "error")
        elif len(password) < 8:
            flash("Your password must be at least 8 characters long.", "error")
        elif password != confirm_password:
            flash("The passwords do not match.", "error")
        else:
            database = get_db()
            with database.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM users WHERE email = %s OR username = %s",
                    (email, username),
                )
                existing_user = cursor.fetchone()

            if existing_user:
                flash("That email address or username is already in use.", "error")
            else:
                with database.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO users (name, username, email, password_hash, role) "
                        "VALUES (%s, %s, %s, %s, 'customer')",
                        (name, username, email, generate_password_hash(password)),
                    )
                database.commit()
                flash("Your account is ready. You can log in now.", "success")
                return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/check-email", methods=("POST",))
def check_email():
    """Check email syntax and domain while someone fills out registration."""
    form_data = request.get_json(silent=True) or {}
    if not isinstance(form_data, dict):
        return jsonify({"valid": False})

    email = form_data.get("email", "")
    if not isinstance(email, str):
        return jsonify({"valid": False})
    email = email.lower()

    has_spaces = any(character.isspace() for character in email)
    if not email or has_spaces or len(email) > 254:
        return jsonify({"valid": False})

    suggested_email = suggest_email_address(email)
    if suggested_email:
        return jsonify({"valid": False, "suggestion": suggested_email})

    return jsonify({"valid": is_valid_email(email)})


@auth_bp.route("/login", methods=("GET", "POST"))
def login():
    """Check the submitted email and password, then start a session."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db().cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Email or password is incorrect.", "error")
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
    """Make sure a user has the required role before opening a page."""
    def decorator(view_function):
        # wraps keeps the protected page's original name and details.
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            # This wrapper runs before the protected page's own function.
            if "user_id" not in session:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))
            if session.get("user_role") != required_role:
                flash("You do not have permission to view that page.", "error")
                return redirect(url_for("index"))
            return view_function(*args, **kwargs)
        return wrapped_view
    return decorator
