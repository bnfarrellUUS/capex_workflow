from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _admin(client):
    db.session.add(User(email="a@x.com", name="Admin",
                        password_hash=hash_password("secret123"), roles='["ADMIN"]'))
    db.session.commit()
    client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})


def _requestor(client):
    db.session.add(User(email="r@x.com", name="Requestor",
                        password_hash=hash_password("secret123"), roles='["REQUESTOR"]'))
    db.session.commit()
    client.post("/api/auth/login", json={"email": "r@x.com", "password": "secret123"})


def test_list_requires_admin(client):
    _requestor(client)
    assert client.get("/api/regions").status_code == 403


def test_create_list_update_region(client, app):
    _admin(client)
    created = client.post("/api/regions", json={"name": "West"})
    assert created.status_code == 201
    region = created.get_json()
    assert region["name"] == "West"
    assert region["active"] is True
    assert region["vp_approver_ids"] == []
    assert region["vp_approver_names"] == []

    listing = client.get("/api/regions").get_json()
    assert any(r["name"] == "West" for r in listing)

    vp = User(email="vp@x.com", name="VP Approver",
              password_hash=hash_password("secret123"), roles='["APPROVER"]')
    db.session.add(vp)
    db.session.commit()

    updated = client.patch(f"/api/regions/{region['id']}", json={
        "name": "West", "active": False, "vp_approver_ids": [vp.id]})
    assert updated.status_code == 200
    body = updated.get_json()
    assert body["active"] is False
    assert body["vp_approver_ids"] == [vp.id]
    assert body["vp_approver_names"] == ["VP Approver"]


def test_duplicate_name_conflicts(client, app):
    _admin(client)
    assert client.post("/api/regions", json={"name": "East"}).status_code == 201
    assert client.post("/api/regions", json={"name": "East"}).status_code == 409


def test_update_unknown_region_404(client, app):
    _admin(client)
    resp = client.patch("/api/regions/nope", json={
        "name": "West", "active": True, "vp_approver_ids": []})
    assert resp.status_code == 404
