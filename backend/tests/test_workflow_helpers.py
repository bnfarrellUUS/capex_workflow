from decimal import Decimal

from app.models import Division, User, ApprovalThreshold, Region
from app.services.workflow_service import (
    compute_required_levels, intended_approvers, effective_assignee,
    eligible_actors, first_assignee, next_pending_level,
)


def _thresholds():
    return [
        ApprovalThreshold(level=1, max_amount=Decimal("50000")),
        ApprovalThreshold(level=2, max_amount=Decimal("250000")),
        ApprovalThreshold(level=3, max_amount=None),
    ]


def test_required_levels_l1():
    assert compute_required_levels(Decimal("30000"), _thresholds()) == 1


def test_required_levels_l2():
    assert compute_required_levels(Decimal("100000"), _thresholds()) == 2


def test_required_levels_l3():
    assert compute_required_levels(Decimal("500000"), _thresholds()) == 3


def test_intended_approvers_l1_are_division_approvers():
    a1 = User(id="a1", email="a@x", name="A", password_hash="x")
    a2 = User(id="a2", email="b@x", name="B", password_hash="x")
    div = Division(number="100", name="F", l1_approvers=[a1, a2])
    assert intended_approvers(1, div, _thresholds()) == [a1, a2]


def test_effective_assignee_prefers_delegate():
    delegate = User(id="d1", email="d@x", name="D", password_hash="x")
    appr = User(id="a1", email="a@x", name="A", password_hash="x",
                delegate_id="d1", delegate=delegate)
    assert effective_assignee(appr) is delegate


def test_eligible_actors_map_through_delegate():
    delegate = User(id="d1", email="d@x", name="D", password_hash="x")
    appr = User(id="a1", email="a@x", name="A", password_hash="x",
                delegate_id="d1", delegate=delegate)
    div = Division(number="100", name="F", l1_approvers=[appr])
    assert eligible_actors(1, div, _thresholds()) == [delegate]
    assert first_assignee(1, div, _thresholds()) is delegate


def test_intended_approvers_l2_come_from_region():
    vp = User(id="vp", email="vp@x", name="VP", password_hash="x")
    div = Division(number="100", name="F", region=Region(name="West", vp_approvers=[vp]))
    assert intended_approvers(2, div, _thresholds()) == [vp]


def test_intended_approvers_l2_empty_without_region():
    div = Division(number="100", name="F")
    assert intended_approvers(2, div, _thresholds()) == []


def test_eligible_actors_exclude_requestor_directly():
    a1 = User(id="a1", email="a@x", name="A", password_hash="x")
    rq = User(id="rq", email="r@x", name="R", password_hash="x")
    div = Division(number="100", name="F", l1_approvers=[a1, rq])
    assert eligible_actors(1, div, _thresholds(), exclude_id="rq") == [a1]


def test_eligible_actors_exclude_requestor_as_delegate():
    rq = User(id="rq", email="r@x", name="R", password_hash="x")
    appr = User(id="a1", email="a@x", name="A", password_hash="x",
                delegate_id="rq", delegate=rq)
    div = Division(number="100", name="F", l1_approvers=[appr])
    assert eligible_actors(1, div, _thresholds(), exclude_id="rq") == []


def test_next_pending_level_skips_empty_levels():
    vp = User(id="vp", email="vp@x", name="VP", password_hash="x")
    div = Division(number="100", name="F", l1_approvers=[],
                   region=Region(name="West", vp_approvers=[vp]))
    assert next_pending_level(0, div, _thresholds()) == 2
    assert next_pending_level(2, div, _thresholds()) is None


def test_next_pending_level_none_when_requestor_is_everyone():
    rq = User(id="rq", email="r@x", name="R", password_hash="x")
    div = Division(number="100", name="F", l1_approvers=[rq])
    assert next_pending_level(0, div, _thresholds(), exclude_id="rq") is None
