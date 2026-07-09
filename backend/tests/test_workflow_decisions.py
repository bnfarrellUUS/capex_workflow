import pytest
from decimal import Decimal

from app.extensions import db
from app.models import ApprovalAction, CapexRequest
from app.services.errors import ServiceError
from app.services.workflow_service import submit, approve, reject, _guarded_transition
from tests.factories import make_user, make_division, set_thresholds, make_draft


def _two_level():
    l1 = make_user("l1")
    l2 = make_user("l2")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds(l2_approver=l2.id)
    req = make_draft(requestor.id, div.id, costs=("100000",))  # needs L1+L2
    submit(req.id, requestor.id)
    return requestor, l1, l2, req


def test_approve_advances_to_next_level(app):
    requestor, l1, l2, req = _two_level()
    result = approve(req.id, l1.id)
    assert result.status == "PENDING_L2"
    assert result.current_level == 2
    assert result.assignee_id == l2.id


def test_final_approval_marks_approved(app):
    requestor, l1, l2, req = _two_level()
    approve(req.id, l1.id)
    result = approve(req.id, l2.id)
    assert result.status == "APPROVED"
    assert result.assignee_id is None


def test_approve_only_by_assignee(app):
    requestor, l1, l2, req = _two_level()
    with pytest.raises(ServiceError):
        approve(req.id, l2.id)  # l2 is not yet the assignee


def test_reject_requires_comment(app):
    requestor, l1, l2, req = _two_level()
    with pytest.raises(ServiceError):
        reject(req.id, l1.id, "")


def test_reject_sets_status_and_records_comment(app):
    requestor, l1, l2, req = _two_level()
    result = reject(req.id, l1.id, "Not this quarter")
    assert result.status == "REJECTED"
    assert result.assignee_id is None
    action = db.session.query(ApprovalAction).filter_by(request_id=req.id, action="REJECTED").one()
    assert action.comment == "Not this quarter"


def test_guarded_transition_rejects_stale_level_or_status(app):
    requestor, l1, l2, req = _two_level()  # current_level == 1, status PENDING_L1
    with pytest.raises(ServiceError):
        _guarded_transition(req.id, 999, "PENDING_L1", {"status": "APPROVED"})  # stale level
    with pytest.raises(ServiceError):
        _guarded_transition(req.id, 1, "PENDING_L2", {"status": "APPROVED"})  # stale status
