from app.extensions import db
from app.models import CapexRequest, Attachment
from app.services.storage import get_storage
from tests.factories import make_user, make_division, make_draft


def _login(client, username, password="secret123"):
    return client.post("/api/auth/login", json={"email": f"{username}@x.com", "password": password})


def test_owner_deletes_own_draft_with_attachment_file(client, app):
    owner = make_user("own", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    storage = get_storage()
    storage.put(f"{req.id}/f.txt", b"data")
    db.session.add(Attachment(request_id=req.id, filename="f.txt",
                              storage_path=f"{req.id}/f.txt", content_type="text/plain",
                              size=4, uploaded_by_id=owner.id))
    db.session.commit()

    _login(client, "own")
    resp = client.delete(f"/api/requests/{req.id}")

    assert resp.status_code == 204
    assert db.session.get(CapexRequest, req.id) is None
    assert db.session.query(Attachment).count() == 0


def test_non_owner_cannot_delete(client, app):
    owner = make_user("own", roles='["REQUESTOR"]')
    make_user("other", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)

    _login(client, "other")
    assert client.delete(f"/api/requests/{req.id}").status_code == 403
    assert db.session.get(CapexRequest, req.id) is not None


def test_only_drafts_can_be_deleted(client, app):
    owner = make_user("own", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    req.status = "PENDING_L1"
    db.session.commit()

    _login(client, "own")
    assert client.delete(f"/api/requests/{req.id}").status_code == 400
    assert db.session.get(CapexRequest, req.id) is not None
