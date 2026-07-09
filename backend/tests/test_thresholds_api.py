from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _admin(client):
    db.session.add(User(username="admin", email="a@x.com", name="Admin",
                        password_hash=hash_password("secret123"), roles='["ADMIN"]'))
    db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})


def test_get_requires_admin(client):
    assert client.get("/api/thresholds").status_code == 401


def test_get_returns_three_levels(client, app):
    _admin(client)
    body = client.get("/api/thresholds").get_json()
    assert [t["level"] for t in body] == [1, 2, 3]


def test_put_updates_thresholds(client, app):
    _admin(client)
    r = client.put("/api/thresholds", json={"thresholds": [
        {"level": 1, "max_amount": "50000", "approver_id": None},
        {"level": 2, "max_amount": "250000", "approver_id": None},
        {"level": 3, "max_amount": None, "approver_id": None},
    ]})
    assert r.status_code == 200
    body = r.get_json()
    lvl1 = next(t for t in body if t["level"] == 1)
    lvl3 = next(t for t in body if t["level"] == 3)
    assert lvl1["max_amount"] == "50000"
    assert lvl3["max_amount"] is None
