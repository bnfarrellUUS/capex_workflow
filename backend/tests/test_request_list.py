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


def test_assigned_worklist_excludes_own_request(client, app):
    viewer = make_user("appr")
    other_approver = make_user("other_appr")
    other_requestor = make_user("other_req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_ids=[viewer.id, other_approver.id])
    viewer.division_id = div.id
    other_requestor.division_id = div.id
    set_thresholds()
    db.session.commit()

    # X: viewer's own request — viewer sits in this division's L1 pool too,
    # but must never see their own request on the assigned worklist.
    x = request_service.create_draft(viewer)
    request_service.update_draft(x.id, viewer, {"equipment_items": [
        {"units": 1, "condition": "NEW", "type": "T", "make": "M", "model": "Mo", "cost": "30000"}]})
    submit(x.id, viewer.id)

    # Y: someone else's request in the same pool — viewer should still see it.
    y = request_service.create_draft(other_requestor)
    request_service.update_draft(y.id, other_requestor, {"equipment_items": [
        {"units": 1, "condition": "NEW", "type": "T", "make": "M", "model": "Mo", "cost": "30000"}]})
    submit(y.id, other_requestor.id)

    _login(client, viewer)
    rows = client.get("/api/requests?scope=assigned").get_json()
    numbers = {r["number"] for r in rows}
    assert x.number not in numbers
    assert y.number in numbers


def test_status_filter(client, app):
    a = make_user("a", roles='["REQUESTOR"]')
    request_service.create_draft(a)  # DRAFT
    _login(client, a)
    assert len(client.get("/api/requests?scope=mine&status=DRAFT").get_json()) == 1
    assert len(client.get("/api/requests?scope=mine&status=APPROVED").get_json()) == 0
