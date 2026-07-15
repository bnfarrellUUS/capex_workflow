from app.extensions import db
from app.models import NotificationLog
from tests.factories import make_user, make_division, set_thresholds


def _login(client, user):
    client.post("/api/auth/login", json={"email": user.email, "password": "secret123"})


def _draft_via_api(client):
    return client.post("/api/requests").get_json()["id"]


def _requestor_in_division():
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    requestor.division_id = div.id
    set_thresholds()
    db.session.commit()
    return approver, requestor


def _add_equipment(client, rid):
    client.patch(f"/api/requests/{rid}", json={
        "equipment_items": [{"units": 1, "condition": "NEW", "type": "T", "make": "M",
                             "model": "Mo", "cost": "30000"}]})


def test_submit_endpoint_routes_and_notifies(client, app):
    approver, requestor = _requestor_in_division()
    _login(client, requestor)
    rid = _draft_via_api(client)
    _add_equipment(client, rid)
    r = client.post(f"/api/requests/{rid}/submit")
    assert r.status_code == 200
    assert r.get_json()["status"] == "PENDING_L1"
    assert db.session.query(NotificationLog).filter_by(type="ASSIGNED").count() == 1


def test_submit_validation_error(client, app):
    approver, requestor = _requestor_in_division()
    _login(client, requestor)
    rid = _draft_via_api(client)  # no equipment
    assert client.post(f"/api/requests/{rid}/submit").status_code == 400


def test_approve_endpoint(client, app):
    approver, requestor = _requestor_in_division()
    _login(client, requestor)
    rid = _draft_via_api(client)
    _add_equipment(client, rid)
    client.post(f"/api/requests/{rid}/submit")
    _login(client, approver)
    r = client.post(f"/api/requests/{rid}/approve", json={})
    assert r.status_code == 200 and r.get_json()["status"] == "APPROVED"


def test_reject_requires_comment_via_api(client, app):
    approver, requestor = _requestor_in_division()
    _login(client, requestor)
    rid = _draft_via_api(client)
    _add_equipment(client, rid)
    client.post(f"/api/requests/{rid}/submit")
    _login(client, approver)
    assert client.post(f"/api/requests/{rid}/reject", json={"comment": ""}).status_code == 400
