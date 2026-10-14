# this creates your flask application and registers the admin, staff, user, and authentication routes
from flask import Flask, render_template
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
        return render_template("index.html")

    @app.route("/design-preview")
    def design_preview():
        return render_template("design_preview.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
