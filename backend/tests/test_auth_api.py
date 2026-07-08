from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _seed_user(**kw):
    d = dict(username="jdoe", email="j@x.com", name="J Doe",
             password_hash=hash_password("secret123"),
             roles='["REQUESTOR"]', active=True)
    d.update(kw)
    u = User(**d)
    db.session.add(u)
    db.session.commit()
    return u


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_login_success_then_me(client, app):
    _seed_user()
    r = client.post("/api/auth/login", json={"username": "jdoe", "password": "secret123"})
    assert r.status_code == 200
    assert r.get_json()["username"] == "jdoe"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["roles"] == ["REQUESTOR"]


def test_login_bad_credentials(client, app):
    _seed_user()
    r = client.post("/api/auth/login", json={"username": "jdoe", "password": "wrong"})
    assert r.status_code == 401


def test_logout_clears_session(client, app):
    _seed_user()
    client.post("/api/auth/login", json={"username": "jdoe", "password": "secret123"})
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_csrf_endpoint_returns_token(client):
    r = client.get("/api/auth/csrf")
    assert r.status_code == 200
    assert r.get_json()["csrfToken"]
