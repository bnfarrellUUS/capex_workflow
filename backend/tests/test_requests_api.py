from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _login(client, username="req", roles='["REQUESTOR"]'):
    u = User(username=username, email=f"{username}@x.com", name=username.title(),
             password_hash=hash_password("secret123"), roles=roles)
    db.session.add(u)
    db.session.commit()
    client.post("/api/auth/login", json={"username": username, "password": "secret123"})
    return u


def test_create_requires_auth(client):
    assert client.post("/api/requests").status_code == 401


def test_create_and_get_draft(client, app):
    _login(client)
    created = client.post("/api/requests")
    assert created.status_code == 201
    body = created.get_json()
    assert body["number"].startswith("CX") and body["status"] == "DRAFT"
    got = client.get(f"/api/requests/{body['id']}")
    assert got.status_code == 200 and got.get_json()["id"] == body["id"]


def test_patch_saves_draft(client, app):
    _login(client)
    rid = client.post("/api/requests").get_json()["id"]
    r = client.patch(f"/api/requests/{rid}", json={
        "description": "Forklift",
        "equipment_items": [{"units": 1, "condition": "NEW", "type": "Forklift",
                             "make": "Toyota", "model": "8", "cost": "30000"}],
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["description"] == "Forklift"
    assert body["equipment_items"][0]["cost"] == "30000"


def test_cannot_get_others_draft(client, app):
    _login(client, "owner")
    rid = client.post("/api/requests").get_json()["id"]
    _login(client, "other")
    assert client.get(f"/api/requests/{rid}").status_code == 403
