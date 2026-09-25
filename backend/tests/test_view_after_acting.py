"""Approvers keep read access to requests they acted on (ADO 5920).

Before, the viewing rule admitted only the requestor, ADMIN/FINANCE and
whoever could act at the current level, so an approver lost the request the
moment their approval moved it on -- a refresh right after approving was a
403. Anyone with an APPROVED or REJECTED action on the request (or on whose
behalf a delegate took one) now keeps read access at every status. It is read
access only: acting still requires being a current approver.
"""

import pytest

from app.extensions import db
from app.services import request_service
from app.services.errors import ServiceError
from app.services.workflow_service import approve, reassign, reject, submit
from tests.factories import make_division, make_draft, make_region, make_user, set_thresholds


def _two_level_request():
    """PENDING_L1 at $100k, so L1's approval moves it to L2."""
    requestor = make_user("req", roles='["REQUESTOR"]')
    l1, vp = make_user("l1"), make_user("vp")
    div = make_division(l1_approver_id=l1.id, region=make_region(name="R", vp_ids=[vp.id]))
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("100000",))
    submit(req.id, requestor.id)
    return req, requestor, l1, vp


def _can_open(req, user):
    db.session.expire_all()
    try:
        request_service.get_request(req.id, user)
        return True
    except ServiceError as e:
        assert e.status == 403
        return False


def test_l1_approver_can_still_open_it_after_it_moves_to_l2(app):
    req, requestor, l1, vp = _two_level_request()
    approve(req.id, l1.id)
    assert _can_open(req, l1)


def test_approvers_can_open_it_once_fully_approved(app):
    req, requestor, l1, vp = _two_level_request()
    approve(req.id, l1.id)
    assert approve(req.id, vp.id).status == "APPROVED"
    assert _can_open(req, l1) and _can_open(req, vp)


def test_the_rejecter_can_open_the_rejected_request(app):
    req, requestor, l1, vp = _two_level_request()
    reject(req.id, l1.id, "Get a second quote")
    assert _can_open(req, l1)


def test_an_approver_whose_delegate_acted_can_open_it(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    cover = make_user("cover")
    away = make_user("away", delegate_id=cover.id)
    div = make_division(l1_approver_id=away.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    approve(req.id, cover.id)                     # acted_for = away
    assert _can_open(req, cover) and _can_open(req, away)


def test_a_reassigned_approver_can_open_it_after_approving(app):
    # The case that surfaced this (2026-09-25 verification of ADO 5907).
    admin = make_user("admin", roles='["ADMIN"]')
    requestor = make_user("req", roles='["REQUESTOR"]')
    gone, helper = make_user("gone"), make_user("helper")
    div = make_division(l1_approver_id=gone.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    gone.active = False
    db.session.commit()
    reassign(req.id, admin.id, helper.id)
    approve(req.id, helper.id)
    assert _can_open(req, helper)


def test_an_uninvolved_approver_still_cannot_open_it(app):
    req, requestor, l1, vp = _two_level_request()
    stranger = make_user("stranger")
    approve(req.id, l1.id)
    assert not _can_open(req, stranger)


def test_read_access_does_not_let_them_act_again(app):
    req, requestor, l1, vp = _two_level_request()
    approve(req.id, l1.id)                        # now PENDING_L2
    with pytest.raises(ServiceError) as exc:
        approve(req.id, l1.id)
    assert exc.value.status == 403


def test_it_leaves_their_assigned_worklist(app):
    req, requestor, l1, vp = _two_level_request()
    approve(req.id, l1.id)
    assert request_service.list_requests(l1, scope="assigned") == []


def test_api_detail_and_pdf_work_for_a_past_approver(app, client):
    req, requestor, l1, vp = _two_level_request()
    approve(req.id, l1.id)
    client.post("/api/auth/login", json={"email": "l1@x.com", "password": "secret123"})
    assert client.get(f"/api/requests/{req.id}").status_code == 200
    assert client.get(f"/api/requests/{req.id}/pdf").status_code == 200


# ---- "Decided by me" list scope --------------------------------------------

def _ids(rows):
    return [r.id for r in rows]


def test_decided_lists_what_you_approved_or_rejected_at_any_status(app):
    req, requestor, l1, vp = _two_level_request()
    other = make_draft(requestor.id, req.division_id, costs=("30000",), number="CX000002")
    submit(other.id, requestor.id)
    approve(req.id, l1.id)                        # req now PENDING_L2
    reject(other.id, l1.id, "No budget")
    assert set(_ids(request_service.list_requests(l1, scope="decided"))) == {req.id, other.id}
    assert _ids(request_service.list_requests(vp, scope="decided")) == []


def test_decided_lists_a_request_once_even_after_several_decisions(app):
    req, requestor, l1, vp = _two_level_request()
    reject(req.id, l1.id, "Fix it")
    from app.services.workflow_service import resubmit
    resubmit(req.id, requestor.id)
    approve(req.id, l1.id)
    assert _ids(request_service.list_requests(l1, scope="decided")) == [req.id]


def test_decided_includes_what_a_delegate_decided_for_you(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    cover = make_user("cover")
    away = make_user("away", delegate_id=cover.id)
    div = make_division(l1_approver_id=away.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    approve(req.id, cover.id)
    assert _ids(request_service.list_requests(away, scope="decided")) == [req.id]
    assert _ids(request_service.list_requests(cover, scope="decided")) == [req.id]


def test_decided_ignores_submitting_and_reassigning(app):
    admin = make_user("admin", roles='["ADMIN"]')
    req, requestor, l1, vp = _two_level_request()
    reassign(req.id, admin.id, vp.id)
    assert _ids(request_service.list_requests(requestor, scope="decided")) == []
    assert _ids(request_service.list_requests(admin, scope="decided")) == []


def test_decided_honours_the_status_filter(app):
    req, requestor, l1, vp = _two_level_request()
    approve(req.id, l1.id)
    assert _ids(request_service.list_requests(l1, scope="decided", status="APPROVED")) == []
    assert _ids(request_service.list_requests(l1, scope="decided", status="PENDING_L2")) == [req.id]


def test_api_decided_scope(app, client):
    req, requestor, l1, vp = _two_level_request()
    approve(req.id, l1.id)
    client.post("/api/auth/login", json={"email": "l1@x.com", "password": "secret123"})
    assert [r["id"] for r in client.get("/api/requests?scope=decided").get_json()] == [req.id]
    assert client.get("/api/requests/export.xlsx?scope=decided").status_code == 200
