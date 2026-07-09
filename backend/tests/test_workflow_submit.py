import pytest
from decimal import Decimal

from app.extensions import db
from app.models import ApprovalAction
from app.services.errors import ServiceError
from app.services.workflow_service import submit
from tests.factories import make_user, make_division, set_thresholds, make_draft


def _setup(cost="30000"):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=(cost,))
    return requestor, approver, req


def test_submit_routes_to_l1_and_sets_totals(app):
    requestor, approver, req = _setup(cost="30000")
    result = submit(req.id, requestor.id)
    assert result.status == "PENDING_L1"
    assert result.current_level == 1
    assert result.required_levels == 1
    assert result.total_cost == Decimal("30000")
    assert result.assignee_id == approver.id


def test_submit_large_amount_requires_three_levels(app):
    requestor, approver, req = _setup(cost="500000")
    result = submit(req.id, requestor.id)
    assert result.required_levels == 3
    assert result.status == "PENDING_L1"  # still enters at L1


def test_submit_writes_submitted_action(app):
    requestor, approver, req = _setup()
    submit(req.id, requestor.id)
    actions = db.session.query(ApprovalAction).filter_by(request_id=req.id).all()
    assert len(actions) == 1 and actions[0].action == "SUBMITTED"


def test_submit_requires_equipment(app):
    approver = make_user("appr")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=())
    with pytest.raises(ServiceError):
        submit(req.id, requestor.id)


def test_submit_requires_l1_approver(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=None)
    set_thresholds()
    req = make_draft(requestor.id, div.id)
    with pytest.raises(ServiceError):
        submit(req.id, requestor.id)


def test_submit_only_drafts(app):
    requestor, approver, req = _setup()
    submit(req.id, requestor.id)
    with pytest.raises(ServiceError):
        submit(req.id, requestor.id)  # already PENDING_L1
