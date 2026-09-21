import os

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db

SSO_ENV_VARS = ("CAPRI_ENABLE_SSO", "CAPRI_SSO_TENANT_ID", "CAPRI_SSO_CLIENT_ID",
                "CAPRI_SSO_CLIENT_SECRET", "CAPRI_SSO_ALLOWED_GROUPS",
                "CAPRI_SSO_REDIRECT_URI")


@pytest.fixture(autouse=True)
def _no_ambient_sso():
    """Keep a developer's .env out of the suite.

    app/config.py calls load_dotenv() at import and this module imports
    create_app at module scope, so CAPRI_ENABLE_SSO=1 in a local .env would
    otherwise 403 every password-login test -- and *which* tests failed would
    move around as tests were added, because it depends on import order. SSO
    tests opt back in with monkeypatch.
    """
    saved = {k: os.environ.pop(k, None) for k in SSO_ENV_VARS}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
