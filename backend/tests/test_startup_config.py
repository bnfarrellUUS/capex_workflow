"""Which config a process runs with, and what it refuses to start without.

APP_BASE_URL is the one switch: a non-local URL means a deployed server, so it
selects ProdConfig (secure cookies, no SQLite fallback, no Outlook) and demands
a real SECRET_KEY. Two independent knobs ("is this production?" and "where does
it live?") would drift apart and let a container run on dev defaults.
"""

import pytest

from app import create_app
from app.config import (INSECURE_DEV_SECRET, DevConfig, ProdConfig, TestConfig,
                        config_from_env, is_local_url)


@pytest.mark.parametrize("url", [None, "", "http://localhost:5100",
                                 "http://127.0.0.1:5100", "http://[::1]:5100"])
def test_local_urls(url):
    assert is_local_url(url)


@pytest.mark.parametrize("url", ["https://capri-dev.uniteduptime.com",
                                 "http://172.16.32.70:8081"])
def test_non_local_urls(url):
    assert not is_local_url(url)


def test_local_base_url_selects_dev_config(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:5100")
    assert config_from_env() is DevConfig


def test_unset_base_url_selects_dev_config(monkeypatch):
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    assert config_from_env() is DevConfig


def test_deployed_base_url_selects_prod_config(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://capri-dev.uniteduptime.com")
    assert config_from_env() is ProdConfig


def test_prod_config_uses_secure_cookies_and_no_outlook():
    assert ProdConfig.SESSION_COOKIE_SECURE is True
    assert ProdConfig.REMEMBER_COOKIE_SECURE is True
    # Inherits BaseConfig's default-off: DevConfig's default-on would try to
    # drive Outlook, which does not exist in a container.
    assert "EMAIL_ENABLED" not in vars(ProdConfig)


class _Deployed(TestConfig):
    APP_BASE_URL = "https://capri-dev.uniteduptime.com"
    SECRET_KEY = "a-real-random-value"


def test_deployed_app_starts_with_a_real_secret():
    assert create_app(_Deployed).config["SECRET_KEY"] == "a-real-random-value"


def test_deployed_app_refuses_the_insecure_default_secret():
    class NoSecret(_Deployed):
        SECRET_KEY = INSECURE_DEV_SECRET

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(NoSecret)


def test_deployed_app_refuses_a_missing_secret():
    class NoSecret(_Deployed):
        SECRET_KEY = None

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(NoSecret)


def test_deployed_app_refuses_plain_http():
    """Secure-only cookies are never sent over http, so sign-in would silently
    fail on every request; refuse at startup instead."""
    class PlainHttp(_Deployed):
        APP_BASE_URL = "http://172.16.32.70:8081"

    with pytest.raises(RuntimeError, match="https"):
        create_app(PlainHttp)


def test_local_app_still_starts_on_the_dev_secret():
    class Local(TestConfig):
        APP_BASE_URL = "http://localhost:5100"
        SECRET_KEY = INSECURE_DEV_SECRET

    create_app(Local)


def test_prod_config_without_a_database_refuses_to_start():
    """No silent SQLite fallback in production (APEX Dev ran on an empty
    database of its own for a day that way)."""
    class NoDb(ProdConfig):
        APP_BASE_URL = "https://capri-dev.uniteduptime.com"
        SECRET_KEY = "a-real-random-value"
        SQLALCHEMY_DATABASE_URI = None

    with pytest.raises(RuntimeError):
        create_app(NoDb)


# --- review follow-ups (2026-09-25) -----------------------------------------

def test_test_config_pins_its_own_base_url_and_email_backend():
    """A developer's .env (e.g. APP_BASE_URL=https://capri-dev...) must not leak
    into the suite through BaseConfig's import-time reads: a non-local URL would
    make every create_app(TestConfig) refuse to start."""
    assert vars(TestConfig)["APP_BASE_URL"] == "http://localhost:5100"
    assert vars(TestConfig)["EMAIL_BACKEND"] == "outlook"


def test_deployed_app_refuses_outlook_with_email_on():
    """Outlook drives a Windows desktop app over COM; on a server every send
    would fail and only be logged."""
    class OutlookOn(_Deployed):
        EMAIL_ENABLED = True
        EMAIL_BACKEND = "outlook"

    with pytest.raises(RuntimeError, match="EMAIL_BACKEND"):
        create_app(OutlookOn)


def test_deployed_app_with_email_off_may_leave_outlook_selected():
    class OutlookOff(_Deployed):
        EMAIL_ENABLED = False
        EMAIL_BACKEND = "outlook"

    create_app(OutlookOff)


def test_deployed_app_refuses_to_start_without_upload_root():
    """Without it, attachments land on the container's own disk, which is wiped
    on every deploy while the database keeps pointing at them."""
    class NoUploads(_Deployed):
        UPLOAD_ROOT = None

    with pytest.raises(RuntimeError, match="UPLOAD_ROOT"):
        create_app(NoUploads)


def test_local_app_may_use_the_default_upload_folder():
    class Local(TestConfig):
        UPLOAD_ROOT = None

    create_app(Local)
