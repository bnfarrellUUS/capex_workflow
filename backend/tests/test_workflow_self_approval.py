import pytest

from app.services.errors import ServiceError
from app.services.workflow_service import submit, approve, eligible_actors
from app.services import threshold_service
from tests.factories import make_user, make_region, make_division, set_thresholds, make_draft


def test_l2_routes_to_region_vp(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    l1 = make_user("l1")
    vp = make_user("vp")
    # Named distinctly from set_thresholds()'s shared default region, so its
    # no-l2_approver default doesn't clobber the VPs we set here.
    region = make_region(name="VP Region", vp_ids=[vp.id])
    div = make_division(l1_approver_id=l1.id, region=region)
    set_thresholds()  # l2_approver left None: threshold row 2 approvers stay empty
    req = make_draft(requestor.id, div.id, costs=("100000",))  # above L1 cap

    result = submit(req.id, requestor.id)
    assert result.status == "PENDING_L1"

    result = approve(req.id, l1.id)
    assert result.status == "PENDING_L2"
    assert result.assignee_id == vp.id
    thresholds = threshold_service.list_thresholds()
    eligible_ids = {u.id for u in eligible_actors(2, div, thresholds)}
    assert vp.id in eligible_ids


def test_requestor_in_l1_pool_is_excluded(app):
    other = make_user("other")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_ids=[other.id, requestor.id])
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)

    result = approve(req.id, other.id)
    assert result.status == "APPROVED"


def test_requestor_cannot_approve_own_request_even_when_pooled(app):
    other = make_user("other")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_ids=[other.id, requestor.id])
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)

    with pytest.raises(ServiceError) as exc_info:
        approve(req.id, requestor.id)
    assert exc_info.value.status == 403
    assert "not assigned to you" in str(exc_info.value)


def test_sole_l1_approver_being_requestor_skips_to_l2(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    vp = make_user("vp")
    region = make_region(name="VP Region", vp_ids=[vp.id])
    div = make_division(l1_approver_id=requestor.id, region=region)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))  # needs only L1

    result = submit(req.id, requestor.id)
    assert result.status == "PENDING_L2"
    assert result.current_level == 2

    result = approve(req.id, vp.id)
    assert result.status == "APPROVED"


def test_requestor_sole_approver_everywhere_blocks_submit(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    region = make_region(name="VP Region", vp_ids=[requestor.id])
    div = make_division(l1_approver_id=requestor.id, region=region)
    set_thresholds(l3_approver=requestor.id)
    req = make_draft(requestor.id, div.id, costs=("500000",))  # needs L1+L2+L3

    with pytest.raises(ServiceError, match="cannot approve their own"):
        submit(req.id, requestor.id)


def test_requestor_as_delegate_is_excluded(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    b = make_user("b")
    a = make_user("a", delegate_id=requestor.id)
    div = make_division(l1_approver_ids=[a.id, b.id])
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)

    with pytest.raises(ServiceError) as exc_info:
        approve(req.id, requestor.id)
    assert exc_info.value.status == 403

    result = approve(req.id, b.id)
    assert result.status == "APPROVED"


def test_skips_empty_middle_level(app):
    requestor = make_user("req", roles='["REQUESTOR"]')
    l1 = make_user("l1")
    l3 = make_user("l3")
    region = make_region(vp_ids=[])  # region exists but has no VPs
    div = make_division(l1_approver_id=l1.id, region=region)
    set_thresholds(l3_approver=l3.id)
    req = make_draft(requestor.id, div.id, costs=("500000",))  # needs L3
    submit(req.id, requestor.id)

    result = approve(req.id, l1.id)
    assert result.status == "PENDING_L3"
    assert result.current_level == 3
