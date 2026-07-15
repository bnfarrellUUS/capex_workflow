from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _admin(client):
    db.session.add(User(email="a@x.com", name="Admin",
                        password_hash=hash_password("secret123"), roles='["ADMIN"]'))
    db.session.commit()
    client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})


def test_list_requires_admin(client):
    assert client.get("/api/users").status_code == 401


def test_admin_can_create_and_list_users(client, app):
    _admin(client)
    r = client.post("/api/users", json={
        "email": "JDoe@x.com", "name": "J Doe",
        "password": "password1", "roles": ["REQUESTOR"], "division_id": None,
    })
    assert r.status_code == 201
    body = r.get_json()
    assert body["email"] == "jdoe@x.com"
    assert body["roles"] == ["REQUESTOR"]
    listing = client.get("/api/users").get_json()
    assert any(u["email"] == "jdoe@x.com" for u in listing)


def test_duplicate_email_conflicts(client, app):
    _admin(client)
    payload = {"email": "dup@x.com", "name": "D",
               "password": "password1", "roles": ["REQUESTOR"]}
    assert client.post("/api/users", json=payload).status_code == 201
    assert client.post("/api/users", json=payload).status_code == 409


def test_short_password_is_validation_error(client, app):
    _admin(client)
    r = client.post("/api/users", json={
        "email": "x@x.com", "name": "X", "password": "short", "roles": ["REQUESTOR"]})
    assert r.status_code == 400


def test_update_user(client, app):
    _admin(client)
    created = client.post("/api/users", json={
        "email": "e@x.com", "name": "E",
        "password": "password1", "roles": ["REQUESTOR"]}).get_json()
    r = client.patch(f"/api/users/{created['id']}", json={
        "name": "Edited", "email": "e@x.com", "roles": ["REQUESTOR", "APPROVER"],
        "division_id": None, "active": False})
    assert r.status_code == 200
    body = r.get_json()
    assert body["name"] == "Edited" and body["active"] is False
    assert set(body["roles"]) == {"REQUESTOR", "APPROVER"}


def test_update_email_duplicate_conflicts(client, app):
    _admin(client)
    client.post("/api/users", json={"email": "aa@x.com", "name": "A",
                                     "password": "password1", "roles": ["REQUESTOR"]})
    b = client.post("/api/users", json={"email": "bb@x.com", "name": "B",
                                        "password": "password1", "roles": ["REQUESTOR"]}).get_json()
    r = client.patch(f"/api/users/{b['id']}", json={
        "name": "B", "email": "aa@x.com",
        "roles": ["REQUESTOR"], "division_id": None, "active": True})
    assert r.status_code == 409


def test_delete_user_without_history_succeeds(client, app):
    _admin(client)
    u = client.post("/api/users", json={"email": "tmp@x.com", "name": "T",
                                        "password": "password1", "roles": ["REQUESTOR"]}).get_json()
    assert client.delete(f"/api/users/{u['id']}").status_code == 200
    assert all(x["email"] != "tmp@x.com" for x in client.get("/api/users").get_json())


def test_delete_user_with_history_blocked(client, app):
    from app.extensions import db
    from app.models import User
    from app.services import request_service
    _admin(client)
    u = client.post("/api/users", json={"email": "h@x.com", "name": "H",
                                        "password": "password1", "roles": ["REQUESTOR"]}).get_json()
    request_service.create_draft(db.session.get(User, u["id"]))
    assert client.delete(f"/api/users/{u['id']}").status_code == 409


def test_cannot_delete_self(client, app):
    from app.extensions import db
    from app.models import User
    from app.services.security import hash_password
    admin = User(email="a@x.com", name="Admin",
                 password_hash=hash_password("secret123"), roles='["ADMIN"]')
    db.session.add(admin)
    db.session.commit()
    client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})
    assert client.delete(f"/api/users/{admin.id}").status_code == 400


def test_admin_reset_password(client, app):
    _admin(client)
    created = client.post("/api/users", json={
        "email": "r@x.com", "name": "R",
        "password": "password1", "roles": ["REQUESTOR"]}).get_json()
    assert client.post(f"/api/users/{created['id']}/reset-password",
                       json={"password": "newpassword1"}).status_code == 200
