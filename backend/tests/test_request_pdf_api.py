from app.extensions import db
from tests.factories import make_user, make_division, make_draft


def _login(client, key):
    client.post("/api/auth/login", json={"email": f"{key}@x.com", "password": "secret123"})


def _request_for(owner):
    div = make_division()
    req = make_draft(owner.id, div.id)
    db.session.commit()
    return req


def test_owner_downloads_the_pdf(client):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _request_for(owner)
    _login(client, "owner")

    r = client.get(f"/api/requests/{req.id}/pdf")

    assert r.status_code == 200
    assert r.mimetype == "application/pdf"
    assert r.data[:5] == b"%PDF-"
    assert f'filename="{req.number}.pdf"' in r.headers["Content-Disposition"]


def test_finance_can_download_any_request(client):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _request_for(owner)
    make_user("fin", roles='["FINANCE"]')
    _login(client, "fin")

    assert client.get(f"/api/requests/{req.id}/pdf").status_code == 200


def test_unrelated_user_is_refused(client):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _request_for(owner)
    make_user("nosy", roles='["REQUESTOR"]')
    _login(client, "nosy")

    assert client.get(f"/api/requests/{req.id}/pdf").status_code == 403


def test_anonymous_is_refused(client):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _request_for(owner)
    assert client.get(f"/api/requests/{req.id}/pdf").status_code == 401


def test_missing_request_is_404(client):
    make_user("owner", roles='["REQUESTOR"]')
    _login(client, "owner")
    assert client.get("/api/requests/nope/pdf").status_code == 404


def test_a_draft_pdf_still_renders(client):
    # Available at any status: a DRAFT simply has no approvals or finance data.
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _request_for(owner)
    _login(client, "owner")

    r = client.get(f"/api/requests/{req.id}/pdf")

    assert r.status_code == 200
    assert r.data[:5] == b"%PDF-"
