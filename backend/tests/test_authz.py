import pytest

from app.extensions import db
from app.models import User
from app.services.security import hash_password
from app.authz import require_roles
from app.services.errors import ServiceError


@pytest.fixture
def app_with_routes(app):
    @app.get("/api/_admin_only")
    @require_roles("ADMIN")
    def _admin_only():
        return {"ok": True}

    @app.get("/api/_boom")
    def _boom():
        raise ServiceError("nope", 409)

    return app


def _make_user(roles):
    u = User(username="u", email="u@x.com", name="U",
             password_hash=hash_password("secret123"), roles=roles)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client):
    return client.post("/api/auth/login", json={"username": "u", "password": "secret123"})


def test_admin_route_401_when_anonymous(app_with_routes):
    client = app_with_routes.test_client()
    assert client.get("/api/_admin_only").status_code == 401


def test_admin_route_403_when_missing_role(app_with_routes):
    client = app_with_routes.test_client()
    _make_user('["REQUESTOR"]')
    _login(client)
    assert client.get("/api/_admin_only").status_code == 403


def test_admin_route_200_when_admin(app_with_routes):
    client = app_with_routes.test_client()
    _make_user('["ADMIN"]')
    _login(client)
    r = client.get("/api/_admin_only")
    assert r.status_code == 200 and r.get_json() == {"ok": True}


def test_service_error_becomes_json(app_with_routes):
    client = app_with_routes.test_client()
    r = client.get("/api/_boom")
    assert r.status_code == 409
    assert r.get_json()["error"] == "nope"
