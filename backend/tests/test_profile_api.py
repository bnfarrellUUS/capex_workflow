from app.extensions import db
from app.models import User
from app.services.security import hash_password, verify_password


def _user(client, username="u", password="secret123"):
    u = User(username=username, email=f"{username}@x.com", name=username.upper(),
             password_hash=hash_password(password), roles='["REQUESTOR"]')
    db.session.add(u)
    db.session.commit()
    client.post("/api/auth/login", json={"username": username, "password": password})
    return u


def test_profile_requires_auth(client):
    assert client.get("/api/profile").status_code == 401


def test_get_profile(client, app):
    _user(client)
    body = client.get("/api/profile").get_json()
    assert body["username"] == "u" and "delegate_id" in body


def test_change_password(client, app):
    u = _user(client)
    r = client.post("/api/profile/password",
                    json={"current_password": "secret123", "new_password": "newsecret123"})
    assert r.status_code == 200
    refreshed = db.session.get(User, u.id)
    assert verify_password("newsecret123", refreshed.password_hash)


def test_change_password_wrong_current(client, app):
    _user(client)
    r = client.post("/api/profile/password",
                    json={"current_password": "WRONG", "new_password": "newsecret123"})
    assert r.status_code == 400


def test_set_delegate(client, app):
    u = _user(client)
    other = User(username="d", email="d@x.com", name="D",
                 password_hash=hash_password("secret123"), roles='["APPROVER"]')
    db.session.add(other)
    db.session.commit()
    r = client.patch("/api/profile", json={"delegate_id": other.id})
    assert r.status_code == 200
    assert db.session.get(User, u.id).delegate_id == other.id


def test_cannot_delegate_to_self(client, app):
    u = _user(client)
    assert client.patch("/api/profile", json={"delegate_id": u.id}).status_code == 400


def test_delegate_options_excludes_self_and_non_approvers(client, app):
    me = _user(client)  # requestor
    appr = User(username="ap", email="ap@x.com", name="Approver",
                password_hash=hash_password("secret123"), roles='["APPROVER"]')
    db.session.add(appr)
    db.session.commit()
    body = client.get("/api/profile/delegate-options").get_json()
    ids = [o["id"] for o in body]
    assert appr.id in ids
    assert me.id not in ids
