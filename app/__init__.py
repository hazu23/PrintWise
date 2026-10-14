"""PrintWise: a centralized platform where customers send print jobs to partner
print shops, and shops run their orders, payments and inventory in one place.

`create_app()` builds the Flask application ("application factory" pattern):
it loads the settings, connects the database layer, registers the pages
(blueprints) and the error pages.
"""
from pathlib import Path

from flask import Flask, g, render_template, request
from werkzeug.exceptions import HTTPException

from config import Config
from app import catalog
from app.db import db
from app.security import CSRFError, add_security_headers, csrf_token, load_current_user, protect_from_csrf


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, instance_path=str(Path(__file__).resolve().parent.parent / "instance"))
    app.config.from_object(config_object)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    if not app.config["TESTING"] and app.config["SECRET_KEY"] == "dev-only-secret-change-me":
        app.logger.warning("SECRET_KEY is not set. Copy .env.example to .env and set a real one.")

    db.init_app(app)
    app.before_request(protect_from_csrf)
    app.before_request(load_current_user)
    app.after_request(add_security_headers)

    _register_blueprints(app)
    _register_template_helpers(app)
    _register_error_pages(app)

    from app.cli import register_commands
    register_commands(app)
    return app


def _register_blueprints(app: Flask) -> None:
    from app.blueprints.account import bp as account_bp
    from app.blueprints.admin import bp as admin_bp
    from app.blueprints.auth import bp as auth_bp
    from app.blueprints.customer import bp as customer_bp
    from app.blueprints.public import bp as public_bp
    from app.blueprints.shop import bp as shop_bp

    for blueprint in (public_bp, auth_bp, account_bp, customer_bp, shop_bp, admin_bp):
        app.register_blueprint(blueprint)


def _register_template_helpers(app: Flask) -> None:
    from app.models import Order

    @app.context_processor
    def inject_globals():
        return {
            "current_user": g.get("user"),
            "csrf_token": csrf_token,
            "catalog": catalog,
            "unread_count": lambda: g.user.unread_notifications() if g.get("user") else 0,
            "pending_orders": lambda: Order.count(shop_id=g.user.shop_id, status="pending")
            if g.get("user") and g.user.is_shop_owner and g.user.shop_id else 0,
        }

    app.jinja_env.globals["status_label"] = lambda status: Order.LABELS.get(status, status)

    @app.template_filter("dt")
    def format_datetime(value):
        return value.strftime("%d %b %Y, %I:%M %p").lstrip("0") if value else ""

    @app.template_filter("day")
    def format_day(value):
        return value.strftime("%d %b %Y").lstrip("0") if value else ""

    @app.template_filter("peso")
    def format_peso(value):
        return "₱{:,.2f}".format(float(value or 0))

    @app.template_filter("filesize")
    def format_filesize(value):
        size = float(value or 0)
        for unit in ("B", "KB", "MB"):
            if size < 1024 or unit == "MB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024


ERROR_TEXT = {
    400: ("Something went wrong with that request", "Go back, refresh the page and try again."),
    403: ("You do not have access to this page", "This page belongs to a different kind of account. Go back to your own dashboard."),
    404: ("We could not find that page", "The link may be old or typed wrong. Check it, or head back to the home page."),
    405: ("That action is not allowed here", "Go back and use the buttons on the page."),
    413: ("That upload is too large", "Files can be up to 25 MB. Compress the file or split it into parts, then try again."),
    500: ("Something broke on our side", "It is not your fault. Try again in a moment. If it keeps happening, tell the shop or the administrator."),
}


def _register_error_pages(app: Flask) -> None:
    def render_error(code, title=None, message=None):
        default_title, default_message = ERROR_TEXT.get(code, ERROR_TEXT[500])
        return render_template("errors/error.html", code=code, title=title or default_title,
                               message=message or default_message), code

    @app.errorhandler(CSRFError)
    def csrf_failed(_error):
        return render_error(400, "Your form expired",
                            "For your safety, forms stop working after you log out or leave a page open for a long time. "
                            "Go back, refresh the page and send the form again.")

    @app.errorhandler(HTTPException)
    def http_error(error):
        return render_error(error.code or 500)

    @app.errorhandler(Exception)
    def unexpected_error(error):
        if app.testing:
            raise error  # let the automated tests show the real traceback
        app.logger.exception("Unhandled error on %s: %s", request.path, error)
        try:
            db.connection.rollback()
        except Exception:  # noqa: BLE001
            pass
        return render_error(500)
