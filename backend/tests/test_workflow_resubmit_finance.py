import pytest
from decimal import Decimal

from app.extensions import db
from app.models import ApprovalAction, CapexRequest
from app.services.errors import ServiceError
from app.services.workflow_service import submit, approve, reject, resubmit, complete_finance
from tests.factories import make_user, make_division, set_thresholds, make_draft


def _rejected():
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    reject(req.id, l1.id, "Fix the quote")
    return requestor, l1, req


def test_resubmit_restarts_at_l1_and_preserves_history(app):
    requestor, l1, req = _rejected()
    result = resubmit(req.id, requestor.id)
    assert result.status == "PENDING_L1"
    assert result.current_level == 1
    actions = [a.action for a in db.session.query(ApprovalAction).filter_by(request_id=req.id).all()]
    assert "SUBMITTED" in actions and "REJECTED" in actions and "RESUBMITTED" in actions


def test_resubmit_only_by_requestor(app):
    requestor, l1, req = _rejected()
    with pytest.raises(ServiceError):
        resubmit(req.id, l1.id)


def test_resubmit_only_when_rejected(app):
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id)
    submit(req.id, requestor.id)  # PENDING_L1, not rejected
    with pytest.raises(ServiceError):
        resubmit(req.id, requestor.id)


def _approved_request():
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    finance = make_user("fin", roles='["FINANCE"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    approve(req.id, l1.id)  # required_levels==1 -> APPROVED
    return requestor, l1, finance, req


def test_complete_finance_sets_costs(app):
    requestor, l1, finance, req = _approved_request()
    result = complete_finance(req.id, finance.id, {
        "cost_machinery": Decimal("30000"),
    })
    assert result.finance_completed is True
    assert result.cost_machinery == Decimal("30000")
    action = db.session.query(ApprovalAction).filter_by(request_id=req.id, action="FINANCE_COMPLETED").one()
    assert action is not None


def test_complete_finance_requires_finance_role(app):
    requestor, l1, finance, req = _approved_request()
    with pytest.raises(ServiceError):
        complete_finance(req.id, l1.id, {})  # l1 is not finance


def test_complete_finance_requires_approved(app):
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    finance = make_user("fin", roles='["FINANCE"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id)
    submit(req.id, requestor.id)  # PENDING_L1, not approved
    with pytest.raises(ServiceError):
        complete_finance(req.id, finance.id, {})
