import os
from pathlib import Path


def load_local_env():
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip("\"'")
        if name:
            os.environ.setdefault(name, value)


load_local_env()


class Config:
    # Use a different, private value before putting the site online.
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "dev-key-change-before-deployment",
    )

    # Connection settings for a local MySQL server (XAMPP).
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "printwise")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"