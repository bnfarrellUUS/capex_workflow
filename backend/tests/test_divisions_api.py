from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _admin(client):
    db.session.add(User(email="a@x.com", name="Admin",
                        password_hash=hash_password("secret123"), roles='["ADMIN"]'))
    db.session.commit()
    client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})


def test_list_requires_admin(client):
    assert client.get("/api/divisions").status_code == 401


def test_create_list_update_division(client, app):
    _admin(client)
    created = client.post("/api/divisions", json={"number": "100", "name": "Field Services"})
    assert created.status_code == 201
    div = created.get_json()
    assert div["number"] == "100" and div["active"] is True

    listing = client.get("/api/divisions").get_json()
    assert any(d["number"] == "100" for d in listing)

    updated = client.patch(f"/api/divisions/{div['id']}", json={
        "number": "100", "name": "Field Svcs", "active": False, "l1_approver_ids": []})
    assert updated.status_code == 200
    assert updated.get_json()["name"] == "Field Svcs"
    assert updated.get_json()["active"] is False


def test_duplicate_number_conflicts(client, app):
    _admin(client)
    assert client.post("/api/divisions", json={"number": "200", "name": "A"}).status_code == 201
    assert client.post("/api/divisions", json={"number": "200", "name": "B"}).status_code == 409


def test_update_division_with_region_id(client, app):
    _admin(client)
    region = client.post("/api/regions", json={"name": "West"}).get_json()
    created = client.post("/api/divisions", json={"number": "300", "name": "C"})
    div = created.get_json()

    updated = client.patch(f"/api/divisions/{div['id']}", json={
        "number": "300", "name": "C", "active": True, "l1_approver_ids": [],
        "region_id": region["id"]})
    assert updated.status_code == 200
    body = updated.get_json()
    assert body["region_id"] == region["id"]
    assert body["region_name"] == "West"


def test_update_division_with_unknown_region_id(client, app):
    _admin(client)
    created = client.post("/api/divisions", json={"number": "301", "name": "D"})
    div = created.get_json()

    updated = client.patch(f"/api/divisions/{div['id']}", json={
        "number": "301", "name": "D", "active": True, "l1_approver_ids": [],
        "region_id": "nope"})
    assert updated.status_code == 400
