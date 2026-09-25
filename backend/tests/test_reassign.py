"""ADMIN reassigns a pending request to a named person (ADO 5907).

The named user joins the current level's approvers for this request only (in
front of the pool, so they are "assigned to"), and the reassignment is cleared
when the request leaves that level. The case it exists for: every approver at
the level has been deactivated, so nobody -- not even an admin -- could act.
"""

import pytest

from app.extensions import db
from app.models import ApprovalAction, NotificationLog
from app.services import request_service, workflow_service
from app.services.errors import ServiceError
from app.services.workflow_service import approve, reassign, reject, submit
from tests.factories import make_division, make_draft, make_region, make_user, set_thresholds


def _stuck_request(cost="30000"):
    """PENDING_L1 whose only L1 approver has since been deactivated."""
    admin = make_user("admin", roles='["ADMIN"]')
    requestor = make_user("req", roles='["REQUESTOR"]')
    gone = make_user("gone")
    helper = make_user("helper", roles='["FINANCE"]')   # any active user will do
    vp = make_user("vp")
    region = make_region(name="VP Region", vp_ids=[vp.id])
    div = make_division(l1_approver_id=gone.id, region=region)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=(cost,))
    submit(req.id, requestor.id)
    gone.active = False
    db.session.commit()
    return req, admin, requestor, gone, helper, vp


def _actors(req):
    db.session.expire_all()
    req = db.session.get(type(req), req.id)
    from app.services import threshold_service
    return [u.id for u in workflow_service.current_actors(req, threshold_service.list_thresholds())]


def test_a_stuck_request_has_no_one_who_can_act(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    assert _actors(req) == []
    with pytest.raises(ServiceError):
        approve(req.id, admin.id)


def test_reassigned_user_can_approve_the_stuck_request(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    reassign(req.id, admin.id, helper.id, comment="Gone left; covering")
    assert _actors(req) == [helper.id]
    assert request_service.request_out(req)["assignee_name"] == "Helper"

    result = approve(req.id, helper.id)
    assert result.status == "APPROVED"


def test_reassigned_user_can_reject(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    reassign(req.id, admin.id, helper.id)
    assert reject(req.id, helper.id, "Not this year").status == "REJECTED"


def test_reassignment_joins_the_pool_in_front(app):
    admin = make_user("admin", roles='["ADMIN"]')
    requestor = make_user("req", roles='["REQUESTOR"]')
    l1, extra = make_user("l1"), make_user("extra")
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)

    reassign(req.id, admin.id, extra.id)
    assert _actors(req) == [extra.id, l1.id]      # the pool can still act


def test_reassignment_is_cleared_when_the_request_leaves_the_level(app):
    req, admin, requestor, gone, helper, vp = _stuck_request(cost="100000")  # needs L2
    reassign(req.id, admin.id, helper.id)
    result = approve(req.id, helper.id)
    assert result.status == "PENDING_L2"
    assert result.reassigned_to_id is None
    assert _actors(req) == [vp.id]                # helper has no say at L2


def test_reassignment_is_cleared_on_reject_and_resubmit(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    reassign(req.id, admin.id, helper.id)
    reject(req.id, helper.id, "Fix the quote")
    assert db.session.get(type(req), req.id).reassigned_to_id is None


def test_history_records_the_reassignment(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    reassign(req.id, admin.id, helper.id, comment="Covering for Gone")
    action = db.session.query(ApprovalAction).filter_by(
        request_id=req.id, action="REASSIGNED").one()
    assert action.actor_id == admin.id
    assert action.level == 1
    assert action.comment == "Reassigned to Helper: Covering for Gone"


def test_history_comment_without_a_note(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    reassign(req.id, admin.id, helper.id)
    action = db.session.query(ApprovalAction).filter_by(action="REASSIGNED").one()
    assert action.comment == "Reassigned to Helper"


@pytest.mark.parametrize("who", ["requestor", "gone"])
def test_cannot_reassign_to_the_requestor_or_an_inactive_user(app, who):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    target = {"requestor": requestor, "gone": gone}[who]
    with pytest.raises(ServiceError) as exc:
        reassign(req.id, admin.id, target.id)
    assert exc.value.status == 400


def test_cannot_reassign_an_unknown_user(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    with pytest.raises(ServiceError) as exc:
        reassign(req.id, admin.id, "no-such-user")
    assert exc.value.status == 400


def test_only_pending_requests_can_be_reassigned(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    reassign(req.id, admin.id, helper.id)
    approve(req.id, helper.id)                    # now APPROVED
    with pytest.raises(ServiceError) as exc:
        reassign(req.id, admin.id, vp.id)
    assert exc.value.status == 400


def test_reassigned_user_can_view_and_sees_it_on_their_worklist(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    reassign(req.id, admin.id, helper.id)
    assert request_service.get_request(req.id, helper).id == req.id
    assert [r.id for r in request_service.list_requests(helper, scope="assigned")] == [req.id]


# ---- API ------------------------------------------------------------------

def _login(client, key):
    client.post("/api/auth/login", json={"email": f"{key}@x.com", "password": "secret123"})


def test_api_admin_reassigns_and_the_new_approver_is_notified(app, client):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    _login(client, "admin")
    resp = client.post(f"/api/requests/{req.id}/reassign",
                       json={"user_id": helper.id, "comment": "Covering"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["assignee_name"] == "Helper"
    assert body["current_approver_names"] == ["Helper"]
    assert db.session.query(NotificationLog).filter_by(
        request_id=req.id, recipient="helper@x.com", type="ASSIGNED").count() == 1


@pytest.mark.parametrize("key", ["req", "vp", "helper"])
def test_api_only_admins_may_reassign(app, client, key):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    _login(client, key)
    resp = client.post(f"/api/requests/{req.id}/reassign", json={"user_id": helper.id})
    assert resp.status_code == 403
    assert db.session.get(type(req), req.id).reassigned_to_id is None


# ---- back into routing ----------------------------------------------------

def test_clearing_returns_the_request_to_its_pool(app):
    admin = make_user("admin", roles='["ADMIN"]')
    requestor = make_user("req", roles='["REQUESTOR"]')
    l1, extra = make_user("l1"), make_user("extra")
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    reassign(req.id, admin.id, extra.id)

    workflow_service.clear_reassignment(req.id, admin.id)
    assert _actors(req) == [l1.id]
    action = db.session.query(ApprovalAction).filter_by(
        request_id=req.id, action="REASSIGNED").order_by(ApprovalAction.created_at.desc()).first()
    assert action.comment == "Returned to normal routing"


def test_clearing_needs_a_reassignment(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    with pytest.raises(ServiceError) as exc:
        workflow_service.clear_reassignment(req.id, admin.id)
    assert exc.value.status == 400


def test_api_only_admins_may_clear(app, client):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    reassign(req.id, admin.id, helper.id)
    _login(client, "helper")
    assert client.delete(f"/api/requests/{req.id}/reassign").status_code == 403
    client.post("/api/auth/logout")
    _login(client, "admin")
    resp = client.delete(f"/api/requests/{req.id}/reassign")
    assert resp.status_code == 200
    assert resp.get_json()["current_approver_names"] == []


# ---- finding stuck requests -----------------------------------------------

def test_summary_flags_a_stuck_request(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    assert request_service.request_summary(req)["stuck"] is True
    reassign(req.id, admin.id, helper.id)
    assert request_service.request_summary(req)["stuck"] is False


def test_a_request_with_approvers_is_not_stuck(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    l1 = make_user("l1")
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    assert request_service.request_summary(req)["stuck"] is False   # DRAFT
    submit(req.id, requestor.id)
    assert request_service.request_summary(req)["stuck"] is False


def test_stuck_status_filter_lists_only_stuck_requests(app, client):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    healthy = make_draft(requestor.id, make_division(number="20", l1_approver_id=vp.id).id,
                         number="CX000002")
    submit(healthy.id, requestor.id)
    rows = request_service.list_requests(admin, scope="all", status="STUCK")
    assert [r.id for r in rows] == [req.id]
    _login(client, "admin")
    body = client.get("/api/requests?scope=all&status=STUCK").get_json()
    assert [r["id"] for r in body] == [req.id]


def test_request_out_names_the_reassignment(app):
    req, admin, requestor, gone, helper, vp = _stuck_request()
    assert request_service.request_out(req)["reassigned_to_name"] is None
    reassign(req.id, admin.id, helper.id)
    assert request_service.request_out(req)["reassigned_to_name"] == "Helper"
