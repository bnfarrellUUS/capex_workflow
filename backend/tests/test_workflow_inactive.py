"""A deactivated user is out of every approver pool.

Before 2026-09-25 the pools were read straight from the division, region and
threshold tables, so deactivating someone (a leaver, or the seeded admin on the
Dev database) left requests routed and emailed to an account nobody could sign
in to -- and if they were a level's only approver, that level stalled.
"""

import pytest

from app.extensions import db
from app.services import threshold_service
from app.services.errors import ServiceError
from app.services.workflow_service import approve, eligible_actors, submit
from tests.factories import make_division, make_draft, make_region, make_user, set_thresholds


def _deactivate(user):
    user.active = False
    db.session.commit()


def _l2_setup(*vps):
    requestor = make_user("req", roles='["REQUESTOR"]')
    l1 = make_user("l1")
    region = make_region(name="VP Region", vp_ids=[v.id for v in vps])
    div = make_division(l1_approver_id=l1.id, region=region)
    return requestor, l1, div


def test_inactive_vp_is_not_an_eligible_actor(app):
    gone, vp = make_user("gone"), make_user("vp")
    _deactivate(gone)
    requestor, l1, div = _l2_setup(gone, vp)
    set_thresholds()
    actors = eligible_actors(2, div, threshold_service.list_thresholds())
    assert [u.id for u in actors] == [vp.id]


def test_request_is_assigned_to_an_active_vp(app):
    gone, vp = make_user("gone"), make_user("vp")
    _deactivate(gone)
    requestor, l1, div = _l2_setup(gone, vp)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("100000",))  # above the L1 cap
    submit(req.id, requestor.id)

    result = approve(req.id, l1.id)
    assert result.status == "PENDING_L2"
    assert result.assignee_id == vp.id


def test_a_level_whose_only_approver_is_inactive_is_skipped(app):
    """Same rule as a level emptied by the self-approval exclusion: the request
    moves on to the next level with someone active, rather than stalling."""
    gone, l3 = make_user("gone"), make_user("l3")
    _deactivate(gone)
    requestor, l1, div = _l2_setup(gone)
    set_thresholds(l3_approver=l3.id)
    req = make_draft(requestor.id, div.id, costs=("100000",))
    submit(req.id, requestor.id)

    result = approve(req.id, l1.id)
    assert result.status == "PENDING_L3"
    assert result.assignee_id == l3.id


def test_an_inactive_approver_cannot_act(app):
    gone, vp = make_user("gone"), make_user("vp")
    requestor, l1, div = _l2_setup(gone, vp)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("100000",))
    submit(req.id, requestor.id)
    approve(req.id, l1.id)
    _deactivate(gone)

    with pytest.raises(ServiceError) as exc:
        approve(req.id, gone.id)
    assert exc.value.status == 403


def test_an_inactive_delegate_does_not_take_the_request(app):
    """An out-of-office delegate who has since been deactivated can't act, so
    the approver keeps their own requests."""
    stand_in = make_user("stand_in")
    vp = make_user("vp", delegate_id=stand_in.id)
    _deactivate(stand_in)
    requestor, l1, div = _l2_setup(vp)
    set_thresholds()
    actors = eligible_actors(2, div, threshold_service.list_thresholds())
    assert [u.id for u in actors] == [vp.id]
