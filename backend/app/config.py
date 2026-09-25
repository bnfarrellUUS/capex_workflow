import os
import tempfile
from datetime import timedelta
from urllib.parse import quote_plus, urlsplit

from dotenv import load_dotenv

# backend/.env holds local secrets (git-ignored). `flask run` loads it itself;
# this makes `python seed.py` and any other entry point see it too.
load_dotenv()


def _database_url(default=None):
    """DATABASE_URL wins; otherwise build one from AZURE_SQL_ODBC, the raw
    ODBC connection string copied from the Azure portal. It has to be
    URL-encoded into ?odbc_connect= because the password contains characters
    (+ # ) !) that a SQLAlchemy URL would mis-parse.

    quote_plus is applied **twice** on purpose: the value is decoded twice on
    the way to pyodbc — once when SQLAlchemy parses the URL query string, and
    again in sqlalchemy/connectors/pyodbc.py, which calls unquote_plus() on
    the already-decoded value. Encoding only once (the pattern in SQLAlchemy's
    own docs) silently turns the literal '+' in the password into a space and
    the login fails with 18456. test_config.py pins the round trip, so a
    SQLAlchemy upgrade that drops the second decode fails there rather than at
    connect time."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    odbc = os.environ.get("AZURE_SQL_ODBC")
    if odbc:
        return "mssql+pyodbc:///?odbc_connect=" + quote_plus(quote_plus(odbc))
    return default


# Signs sessions on a developer's PC only. It is in the repo, so create_app
# refuses to start a deployed server (non-local APP_BASE_URL) that still uses it.
INSECURE_DEV_SECRET = "dev-insecure-change-me"


def is_local_url(url):
    """True for an unset/empty URL or one pointing at this machine."""
    if not url:
        return True
    return urlsplit(url).hostname in ("localhost", "127.0.0.1", "::1")


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", INSECURE_DEV_SECRET)
    # Starting password for new accounts and admin resets; the owner must
    # replace it on first login (User.must_change_password).
    DEFAULT_PASSWORD = "Welcome@1"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # overridden in prod
    # Flask-Login remember-me cookie (login_user(remember=True)): keeps users
    # signed in across browser restarts so email deep links don't force a login.
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = False  # overridden in prod
    WTF_CSRF_TIME_LIMIT = None
    UPLOAD_ROOT = os.environ.get("UPLOAD_ROOT")  # None -> instance/uploads

    # Email delivery. The routing logic in services/notify.py always records a
    # NotificationLog; EMAIL_ENABLED additionally sends the message through the
    # local Outlook desktop app (services/email_outlook.py). While running
    # locally we redirect every message to EMAIL_REDIRECT_TO and note the
    # intended recipient in the body; clear it when real delivery is wanted.
    EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "0") == "1"
    EMAIL_REDIRECT_TO = os.environ.get("EMAIL_REDIRECT_TO", "bryan.farrell@uniteduptime.com")
    # Which sender delivers: "outlook" (the desktop app over COM; Windows only)
    # or "sendgrid" (services/email_sendgrid.py; what a container uses). With
    # EMAIL_ENABLED and sendgrid, create_app refuses to start unless the key and
    # a from-address are set -- SendGrid silently drops mail from an unverified
    # sender, so EMAIL_FROM must be one verified there.
    EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "outlook").strip().lower()
    SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
    EMAIL_FROM = os.environ.get("EMAIL_FROM")
    EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "CAPRI")
    # Base URL used to build deep links in notification emails. On a server set
    # this to the real host (e.g. https://capri.uniteduptime.com).
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5100")


class DevConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = _database_url("sqlite:///capex_dev.db")
    # Send via Outlook by default in dev; set EMAIL_ENABLED=0 to silence it.
    EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "1") == "1"


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_ROOT = os.path.join(tempfile.gettempdir(), "capex_test_uploads")
    EMAIL_ENABLED = False


class ProdConfig(BaseConfig):
    # No SQLite fallback: with neither DATABASE_URL nor AZURE_SQL_ODBC set this
    # is None and Flask-SQLAlchemy refuses to start, rather than the server
    # quietly running on an empty database of its own.
    SQLALCHEMY_DATABASE_URI = _database_url()
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


def config_from_env():
    """APP_BASE_URL is the single switch: a non-local URL is a deployed server.

    Read at call time, not import time, so it is testable. There is deliberately
    no separate "environment" flag -- two knobs drift apart, and a container
    left on DevConfig would sign sessions with INSECURE_DEV_SECRET.
    """
    if is_local_url(os.environ.get("APP_BASE_URL")):
        return DevConfig
    return ProdConfig
