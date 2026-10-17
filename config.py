import os


class Config:
    # Local-development fallback. Set SECRET_KEY in the host environment for deployment.
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-key-change-before-deployment",
    )

    # Local-development defaults for a typical XAMPP MySQL installation.
    # Override these through operating-system environment variables when needed.
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "printwise")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
