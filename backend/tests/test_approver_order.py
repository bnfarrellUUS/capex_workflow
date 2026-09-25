"""Approver pools keep the order an admin sets (the TransferList's up/down).

Before 2026-09-25 the order was lost twice: the services loaded users with
`WHERE id IN (...)` (database order, not submitted order), and the pool tables
had no position column. The first approver is the request's "assigned to", so
the name shown on requests and worklists was effectively arbitrary.
"""

from app.extensions import db
from app.models import ApprovalThreshold, Division, Region
from app.services import division_service, region_service, threshold_service
from app.services.workflow_service import submit
from tests.factories import make_division, make_draft, make_user, set_thresholds


def _fresh(model, id_):
    """Re-read from the database, not from the session's in-memory list."""
    db.session.expire_all()
    return db.session.get(model, id_)


def _ids(users):
    return [u.id for u in users]


def _three():
    # Keys chosen so that alphabetical and id order differ from the order set.
    return make_user("zed"), make_user("amy"), make_user("mid")


def test_region_vp_order_is_kept_on_create_and_update(app):
    z, a, m = _three()
    region = region_service.create_region(name="North", vp_approver_ids=[z.id, a.id, m.id])
    assert _ids(_fresh(Region, region.id).vp_approvers) == [z.id, a.id, m.id]

    region_service.update_region(region.id, name="North", active=True,
                                 vp_approver_ids=[m.id, z.id])
    assert _ids(_fresh(Region, region.id).vp_approvers) == [m.id, z.id]


def test_division_l1_order_is_kept(app):
    z, a, m = _three()
    div = make_division()
    division_service.update_division(div.id, number=div.number, name=div.name, active=True,
                                     l1_approver_ids=[m.id, z.id, a.id],
                                     region_id=div.region_id)
    assert _ids(_fresh(Division, div.id).l1_approvers) == [m.id, z.id, a.id]

    division_service.update_division(div.id, number=div.number, name=div.name, active=True,
                                     l1_approver_ids=[a.id, m.id], region_id=div.region_id)
    assert _ids(_fresh(Division, div.id).l1_approvers) == [a.id, m.id]


def test_threshold_approver_order_is_kept(app):
    z, a, m = _three()
    set_thresholds()
    rows = {t.level: t for t in threshold_service.list_thresholds()}
    threshold_service.set_thresholds([
        {"level": 1, "max_amount": rows[1].max_amount, "approver_ids": []},
        {"level": 2, "max_amount": rows[2].max_amount, "approver_ids": []},
        {"level": 3, "max_amount": None, "approver_ids": [m.id, a.id, z.id]},
    ])
    assert _ids(_fresh(ApprovalThreshold, rows[3].id).approvers) == [m.id, a.id, z.id]


def test_duplicate_and_unknown_ids_are_dropped_without_reordering(app):
    z, a, m = _three()
    region = region_service.create_region(
        name="South", vp_approver_ids=[a.id, "no-such-user", z.id, a.id, "", m.id])
    assert _ids(_fresh(Region, region.id).vp_approvers) == [a.id, z.id, m.id]


def test_the_first_approver_in_the_set_order_is_the_assignee(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    z, a, m = _three()
    div = make_division()
    division_service.update_division(div.id, number=div.number, name=div.name, active=True,
                                     l1_approver_ids=[m.id, z.id, a.id],
                                     region_id=div.region_id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    assert submit(req.id, requestor.id).assignee_id == m.id
