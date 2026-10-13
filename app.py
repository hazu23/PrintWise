# this creates your flask application and registers the admin, staff, user, and authentication routes
from flask import Flask, redirect, url_for
from config import Config
from users import admin_bp, staff_bp, user_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # register blueprints
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(user_bp)

    # home page
    @app.route("/")
    def index():
        return "Welcome to PrintWise!"

    # temporary dashboards
    @app.route("/admin/dashboard")
    def admin_dashboard():
        return "Admin Dashboard"

    @app.route("/staff/dashboard")
    def staff_dashboard():
        return "Staff Dashboard"

    @app.route("/user/dashboard")
    def user_dashboard():
        return "User Dashboard"

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
