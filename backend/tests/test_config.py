"""_database_url builds the Azure SQL URL by URL-encoding AZURE_SQL_ODBC.

The encoding has to survive *two* decodes before pyodbc sees it (SQLAlchemy's
URL query parse, then unquote_plus in sqlalchemy/connectors/pyodbc.py), so the
round trip is pinned here: a password with a literal '+' used to arrive with a
space instead and the login failed with 18456.
"""

import sqlalchemy
from sqlalchemy.engine import make_url

from app.config import _database_url

# A '+' and a '%' in the password are the characters the double decode eats.
ODBC = (
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=example.database.windows.net;Database=capri;"
    "Uid=someadmin;Pwd=aB3+cD4%eF5)gH6#iJ7!;"
    "Encrypt=yes;TrustServerCertificate=no"
)


def test_database_url_prefers_explicit_database_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///explicit.db")
    monkeypatch.setenv("AZURE_SQL_ODBC", ODBC)
    assert _database_url() == "sqlite:///explicit.db"


def test_database_url_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("AZURE_SQL_ODBC", raising=False)
    assert _database_url("sqlite:///fallback.db") == "sqlite:///fallback.db"


def test_odbc_string_reaches_pyodbc_byte_for_byte(monkeypatch):
    """The whole point: what pyodbc is handed must equal the raw .env string."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AZURE_SQL_ODBC", ODBC)

    url = make_url(_database_url())
    engine = sqlalchemy.create_engine(url)
    cargs, _ = engine.dialect.create_connect_args(url)

    assert cargs[0] == ODBC
