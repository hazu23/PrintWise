# Application configuration
import os

class Config:
    SECRET_KEY = os.environ.get("PRINTWISE_SECRET_KEY", "dev-key-change-before-deployment")

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "printwise")
