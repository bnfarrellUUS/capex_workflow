import os
import tempfile


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # overridden in prod
    WTF_CSRF_TIME_LIMIT = None
    UPLOAD_ROOT = os.environ.get("UPLOAD_ROOT")  # None -> instance/uploads


class DevConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///capex_dev.db"
    )


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_ROOT = os.path.join(tempfile.gettempdir(), "capex_test_uploads")


class ProdConfig(BaseConfig):
    # e.g. mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server
    # Read lazily so importing the module never fails when the var is unset
    # (dev/test); deployment must set DATABASE_URL.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SESSION_COOKIE_SECURE = True
