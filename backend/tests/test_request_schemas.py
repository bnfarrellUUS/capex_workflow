import pytest
from decimal import Decimal
from pydantic import ValidationError

from app.schemas.request import RequestDraft, RequestSubmit, EquipmentItemIn


def test_draft_allows_empty():
    d = RequestDraft()
    assert d.equipment_items == []
    assert d.description is None


def test_draft_accepts_partial():
    d = RequestDraft(description="Forklift", budgeted=True)
    assert d.description == "Forklift" and d.budgeted is True


def test_draft_accepts_budget_amount():
    assert RequestDraft(budget_amount="45000").budget_amount == Decimal("45000")


def test_draft_rejects_negative_budget_amount():
    with pytest.raises(ValidationError):
        RequestDraft(budget_amount="-1")


def test_submit_requires_core_fields():
    with pytest.raises(ValidationError):
        RequestSubmit(description="x")  # missing the rest


def test_submit_ok_with_all_required():
    s = RequestSubmit(
        description="Forklift", justification="Needed", effect_on_operations="Faster",
        division_id="div1",
        equipment_items=[EquipmentItemIn(units=1, condition="NEW", type="Forklift",
                                         make="Toyota", model="8FGU25", cost="30000")],
    )
    assert s.division_id == "div1"
    assert s.equipment_items[0].cost == 30000


def test_comment_in_strips_and_requires_a_body():
    from pydantic import ValidationError
    from app.schemas.request import CommentIn

    assert CommentIn(body="  Real question  ").body == "Real question"
    for bad in ("", "   ", "x" * 4001):
        with pytest.raises(ValidationError):
            CommentIn(body=bad)
