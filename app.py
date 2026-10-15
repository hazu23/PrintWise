# creates my flask application and registers the admin, staff, user, and authentication routes
from flask import Flask, render_template
from config import Config
from users import admin_bp, auth_bp, staff_bp, user_bp
from users.db import close_db, init_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # creates the accounts table after app is starting
    with app.app_context():
        init_db()
    app.teardown_appcontext(close_db)

    # register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(user_bp)

    # home page
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/design-idea")
    def design_preview():
        return render_template("test.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
