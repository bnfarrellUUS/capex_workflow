from app.extensions import db
from app.services import request_service
from app.services.workflow_service import submit
from tests.factories import make_user, make_division, set_thresholds


def _login(client, user):
    client.post("/api/auth/login", json={"email": user.email, "password": "secret123"})


def test_list_scope_mine(client, app):
    a = make_user("a", roles='["REQUESTOR"]')
    b = make_user("b", roles='["REQUESTOR"]')
    request_service.create_draft(a)
    request_service.create_draft(b)
    _login(client, a)
    rows = client.get("/api/requests?scope=mine").get_json()
    assert len(rows) == 1


def test_list_scope_assigned(client, app):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    requestor.division_id = div.id
    set_thresholds()
    db.session.commit()
    d = request_service.create_draft(requestor)
    request_service.update_draft(d.id, requestor, {"equipment_items": [
        {"units": 1, "condition": "NEW", "type": "T", "make": "M", "model": "Mo", "cost": "30000"}]})
    submit(d.id, requestor.id)
    _login(client, approver)
    rows = client.get("/api/requests?scope=assigned").get_json()
    assert len(rows) == 1 and rows[0]["status"] == "PENDING_L1"


def test_assigned_worklist_visible_to_every_pool_approver(client, app):
    cfo = make_user("cfo")
    ceo = make_user("ceo")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_ids=[cfo.id, ceo.id])
    requestor.division_id = div.id
    set_thresholds()
    db.session.commit()
    d = request_service.create_draft(requestor)
    request_service.update_draft(d.id, requestor, {"equipment_items": [
        {"units": 1, "condition": "NEW", "type": "T", "make": "M", "model": "Mo", "cost": "30000"}]})
    submit(d.id, requestor.id)
    # both approvers see it on their worklist, not just the displayed assignee
    for approver in (cfo, ceo):
        _login(client, approver)
        rows = client.get("/api/requests?scope=assigned").get_json()
        assert len(rows) == 1


def test_status_filter(client, app):
    a = make_user("a", roles='["REQUESTOR"]')
    request_service.create_draft(a)  # DRAFT
    _login(client, a)
    assert len(client.get("/api/requests?scope=mine&status=DRAFT").get_json()) == 1
    assert len(client.get("/api/requests?scope=mine&status=APPROVED").get_json()) == 0
