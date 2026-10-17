#Registration, login, logout, and simple role checks

# import re  # Temporarily unused; this was used to validate usernames.
from functools import wraps

from flask import flash, jsonify, redirect, render_template, request, session, url_for  # these are used by the login and registration routes
from werkzeug.security import check_password_hash, generate_password_hash
from email_validator import EmailNotValidError, validate_email

from users import auth_bp
from users.db import get_db  # provides a connection to the database

EMAIL_PROVIDER_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "msn.com",
    "yahoo.com",
    "yahoo.co.uk",
    "yahoo.ca",
    "yahoo.com.au",
    "ymail.com",
    "rocketmail.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "gmx.com",
    "gmx.net",
    "mail.com",
    "zoho.com",
    "fastmail.com",
    "hey.com",
    "tuta.com",
    "tutanota.com",
    "yandex.com",
    "yandex.ru",
}


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
    """Check email format and whether its domain can receive email."""
    if not email or len(email) > 100 or any(character.isspace() for character in email):
        return False

    try:
        # Check the domain's mail records; this supports different email providers.
        validated_email = validate_email(email, check_deliverability=True, timeout=3)
    except EmailNotValidError:
        return False

    # Only allow known email-provider domains, so website domains like youtube.com are rejected.
    domain = validated_email.domain.lower().rstrip(".")
    return domain in EMAIL_PROVIDER_DOMAINS


def get_registration_error(name, email, password, confirm_password):
    """Return an error message when a registration field is invalid."""
    if not name or not email or not password:
        return "Please fill in every field."

    if not is_valid_full_name(name):
        return (
            "Enter a full name with at least two words and six letters. "
            "Use letters and single spaces; a middle initial may end with a period, "
            "and suffixes like Jr., Sr., or III are allowed."
        )

    # Username validation is temporarily disabled with the registration field.
    # if not re.fullmatch(r"[a-z0-9_.]{3,20}", username):
    #     return "Enter a valid username."

    if any(character.isspace() for character in email):
        return "Spaces are not allowed in an email address."
    if len(email) > 100:
        return "Email addresses can't be longer than 100 characters."
    if not is_valid_email(email):
        return "Enter a valid email address."

    if any(character.isspace() for character in password) or any(
        character.isspace() for character in confirm_password
    ):
        return "Spaces aren't allowed in passwords."
    if len(password) < 8:
        return "Your password must be at least 8 characters long."
    if not any(character.isalpha() for character in password):
        return "Your password must include at least one letter."
    if not any("0" <= character <= "9" for character in password):
        return "Your password must include at least one number."
    if not any(not character.isalnum() and not character.isspace() for character in password):
        return "Your password must include at least one special character."
    if password != confirm_password:
        return "The passwords do not match."

    return None


def start_user_session(user):
    """Remember the logged-in user's ID, name, and role for later requests."""
    # Clear any old login data before starting this user's session.
    session.clear()
    # Store only the information the app needs to recognize this user.
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_role"] = user["role"]


@auth_bp.route("/register", methods=("GET", "POST"))
def register():
    """Create a customer account from the registration form."""
    if request.method == "POST":
        name = request.form.get("name", "")
        # username = request.form.get("username", "").lower()  # Temporarily disabled.
        email = request.form.get("email", "").lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        error_message = get_registration_error(name, email, password, confirm_password)
        if error_message:
            flash(error_message, "error")
        else:
            database = get_db()
            with database.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM users WHERE email = %s",
                    (email,),
                )
                # Username checks are disabled; the previous query also checked username:
                # cursor.execute("SELECT id FROM users WHERE email = %s OR username = %s", (email, username))
                existing_user = cursor.fetchone()

            if existing_user:
                flash("That email address is already in use.", "error")
            else:
                with database.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO users (name, email, password_hash, role) "
                        "VALUES (%s, %s, %s, 'customer')",
                        (name, email, generate_password_hash(password)),
                    )
                    # The previous insert also saved username, which is disabled for now.
                    # cursor.execute("INSERT INTO users (name, username, email, password_hash, role) VALUES (%s, %s, %s, %s, 'customer')", (name, username, email, generate_password_hash(password)))
                database.commit()
                flash("Your account is ready. You can log in now.", "success")
                return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/check-email", methods=("POST",))
def check_email():
    """Check an email address while someone fills out the registration form."""
    form_data = request.get_json(silent=True) or {}
    if not isinstance(form_data, dict):
        return jsonify({"valid": False})

    email = form_data.get("email", "")
    if not isinstance(email, str):
        return jsonify({"valid": False})

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
            start_user_session(user)
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
    # Removing these values logs the user out.
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
