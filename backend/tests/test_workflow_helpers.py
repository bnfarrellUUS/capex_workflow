from decimal import Decimal

from app.models import Division, User, ApprovalThreshold
from app.services.workflow_service import (
    compute_required_levels, intended_approvers, effective_assignee,
    eligible_actors, first_assignee,
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
    a1 = User(id="a1", username="a", email="a@x", name="A", password_hash="x")
    a2 = User(id="a2", username="b", email="b@x", name="B", password_hash="x")
    div = Division(number="100", name="F", l1_approvers=[a1, a2])
    assert intended_approvers(1, div, _thresholds()) == [a1, a2]


def test_effective_assignee_prefers_delegate():
    delegate = User(id="d1", username="d", email="d@x", name="D", password_hash="x")
    appr = User(id="a1", username="a", email="a@x", name="A", password_hash="x",
                delegate_id="d1", delegate=delegate)
    assert effective_assignee(appr) is delegate


def test_eligible_actors_map_through_delegate():
    delegate = User(id="d1", username="d", email="d@x", name="D", password_hash="x")
    appr = User(id="a1", username="a", email="a@x", name="A", password_hash="x",
                delegate_id="d1", delegate=delegate)
    div = Division(number="100", name="F", l1_approvers=[appr])
    assert eligible_actors(1, div, _thresholds()) == [delegate]
    assert first_assignee(1, div, _thresholds()) is delegate
