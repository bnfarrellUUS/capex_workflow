import io
from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _login(client, username="req", roles='["REQUESTOR"]'):
    u = User(email=f"{username}@x.com", name=username.title(),
             password_hash=hash_password("secret123"), roles=roles)
    db.session.add(u)
    db.session.commit()
    client.post("/api/auth/login", json={"email": f"{username}@x.com", "password": "secret123"})
    return u


def test_upload_download_delete(client, app):
    _login(client)
    rid = client.post("/api/requests").get_json()["id"]
    up = client.post(f"/api/requests/{rid}/attachments",
                     data={"file": (io.BytesIO(b"quote-bytes"), "quote.pdf")},
                     content_type="multipart/form-data")
    assert up.status_code == 200
    att = up.get_json()["attachments"][0]
    dl = client.get(f"/api/requests/{rid}/attachments/{att['id']}")
    assert dl.status_code == 200 and dl.data == b"quote-bytes"
    d = client.delete(f"/api/requests/{rid}/attachments/{att['id']}")
    assert d.status_code == 200 and d.get_json()["attachments"] == []
