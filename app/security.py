"""Security helpers: CSRF protection, login sessions, access control, signed tokens.

How the pieces work
- Passwords are hashed in models/user.py (never stored in plain text).
- A login stores only the user's id in Flask's signed session cookie.
- Every POST form carries a secret CSRF token that must match the one in the
  session, so another website cannot submit forms on a user's behalf.
- Jinja escapes all output by default, which protects against XSS.
"""
import hmac
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import abort, current_app, flash, g, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.exceptions import BadRequest

from app.models import User

CSRF_KEY = "_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CSRFError(BadRequest):
    description = "The form could not be verified."


# ----- CSRF ------------------------------------------------------------------
def csrf_token() -> str:
    token = session.get(CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_KEY] = token
    return token


def protect_from_csrf():
    """Runs before every request. Rejects state-changing requests without a valid token."""
    if request.method in SAFE_METHODS:
        return
    sent = (request.form.get("_csrf") or request.headers.get("X-CSRFToken") or "").encode()
    expected = session.get(CSRF_KEY, "").encode()
    if not expected or not hmac.compare_digest(sent, expected):
        raise CSRFError()


# ----- sessions -----------------------------------------------------------------
def load_current_user():
    """Runs before every request: look up the logged-in user, if any."""
    g.user = None
    user_id = session.get("uid")
    if user_id:
        user = User.get(user_id)
        if user and user.is_active:
            g.user = user
        else:
            session.clear()
    if g.user and g.user.must_change_password:
        allowed = {"auth.first_login_setup", "auth.logout", "static"}
        if request.endpoint not in allowed:
            return redirect(url_for("auth.first_login_setup"))
    return None


def login_user(user: User) -> None:
    session.clear()  # a fresh session on every login prevents session fixation
    session["uid"] = user.id
    session.permanent = True
    session[CSRF_KEY] = secrets.token_urlsafe(32)


def logout_user() -> None:
    session.clear()


# ----- access control -----------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "info")
            target = request.full_path.rstrip("?") if request.method == "GET" else None
            return redirect(url_for("auth.login", next=target) if target else url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    """Allow only the listed roles; everyone else gets a 403 page."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def safe_next_url(target, fallback: str) -> str:
    """Only follow redirects that stay on this site (blocks open-redirect tricks)."""
    if not target:
        return fallback
    parts = urlparse(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return fallback
    return target


# ----- signed, expiring tokens (email verification, password reset) -----------------
def _serializer(purpose: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=f"printwise-{purpose}")


def make_token(purpose: str, payload) -> str:
    return _serializer(purpose).dumps(payload)


def read_token(purpose: str, token: str, max_age_seconds: int):
    """Return the payload, or None when the token is wrong or expired."""
    try:
        return _serializer(purpose).loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None


# ----- response headers ----------------------------------------------------------------
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
    "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com data:",
    "img-src 'self' data:",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
])


def add_security_headers(response):
    response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if g.get("user") is not None:
        response.headers["Cache-Control"] = "no-store"  # do not keep private pages in the browser cache
    return response
