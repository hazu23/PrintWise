"""Command line tools, run from the project folder:

    flask --app run init-db            create the database and tables
    flask --app run init-db --reset    delete everything and start again
    flask --app run create-admin       create an administrator account
    flask --app run seed-demo          add fictional demo shops, customers and orders
"""
import re

import click
from flask import current_app

from app.db import db
from app.models import Admin, User
from app.validators import password_problem


def _create_mysql_database(config) -> None:
    """Create the MySQL database if it does not exist yet (the tables come next)."""
    import pymysql
    name = config["DB_NAME"]
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise click.ClickException("DB_NAME may only contain letters, numbers and underscores.")
    try:
        connection = pymysql.connect(host=config["DB_HOST"], port=config["DB_PORT"],
                                     user=config["DB_USER"], password=config["DB_PASSWORD"])
    except pymysql.err.OperationalError as error:
        raise click.ClickException(
            f"Could not connect to MySQL at {config['DB_HOST']}:{config['DB_PORT']} ({error.args[-1]}).\n"
            "Open the XAMPP Control Panel, start MySQL, and check DB_USER and DB_PASSWORD in your .env file.")
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        connection.commit()


def register_commands(app):
    @app.cli.command("init-db")
    @click.option("--reset", is_flag=True, help="Delete all existing tables and data first.")
    def init_db(reset):
        """Create the database and its tables."""
        if current_app.config["DB_BACKEND"] == "mysql":
            _create_mysql_database(current_app.config)
        if reset:
            if not click.confirm("This deletes ALL PrintWise data. Continue?"):
                raise click.Abort()
            db.drop_schema()
        db.create_schema()
        click.echo("Database is ready.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt="Full name")
    @click.option("--username", prompt="Username")
    @click.option("--email", prompt="Email")
    @click.password_option()
    def create_admin(name, username, email, password):
        """Create an administrator account."""
        username, email = username.strip().lower(), email.strip().lower()
        problem = password_problem(password)
        if problem:
            raise click.ClickException(f"Password: {problem}")
        if User.username_taken(username) or User.email_taken(email):
            raise click.ClickException("That username or email is already used.")
        admin = Admin(full_name=name.strip(), username=username, email=email, email_verified=1)
        admin.set_password(password)
        admin.save()
        click.echo(f"Administrator '{username}' created.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Add fictional demo data so every page has something to show."""
        from app.seed import seed_demo
        for line in seed_demo():
            click.echo(line)
