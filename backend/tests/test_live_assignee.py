"""A request's "assigned to" is its current first approver, not a snapshot.

assignee_id is written when a request enters a level, and nothing updates it
afterwards. Before 2026-09-25 the requests list and detail page showed that
stored value, so deactivating the approver or reordering the pool left the
page naming someone who could no longer act, while "current approvers" (live)
said otherwise.
"""

from app.extensions import db
from app.services import division_service, request_service
from app.services.workflow_service import submit
from tests.factories import make_division, make_draft, make_user, set_thresholds


def _pending_request():
    requestor = make_user("req", roles='["REQUESTOR"]')
    first, second = make_user("first"), make_user("second")
    div = make_division()
    division_service.update_division(div.id, number=div.number, name=div.name, active=True,
                                     l1_approver_ids=[first.id, second.id],
                                     region_id=div.region_id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    return req, div, first, second


def _shown(req):
    db.session.expire_all()
    req = db.session.get(type(req), req.id)
    out, row = request_service.request_out(req), request_service.request_summary(req)
    return out["assignee_name"], out["assignee_id"], row["assignee_name"]


def test_assignee_is_the_first_approver_at_submit(app):
    req, div, first, second = _pending_request()
    assert _shown(req) == ("First", first.id, "First")


def test_assignee_follows_deactivation(app):
    req, div, first, second = _pending_request()
    first.active = False
    db.session.commit()
    assert _shown(req) == ("Second", second.id, "Second")


def test_assignee_follows_a_pool_reorder(app):
    req, div, first, second = _pending_request()
    division_service.update_division(div.id, number=div.number, name=div.name, active=True,
                                     l1_approver_ids=[second.id, first.id],
                                     region_id=div.region_id)
    assert _shown(req) == ("Second", second.id, "Second")


def test_a_finished_request_has_no_assignee(app):
    req, div, first, second = _pending_request()
    from app.services.workflow_service import approve
    approve(req.id, first.id)
    assert _shown(req) == (None, None, None)


def test_no_deactivated_name_when_the_whole_pool_is_inactive(app):
    """With nobody eligible, the old snapshot would name the deactivated
    approver; show no assignee instead of someone who cannot act."""
    req, div, first, second = _pending_request()
    first.active = second.active = False
    db.session.commit()
    assert _shown(req) == (None, None, None)
