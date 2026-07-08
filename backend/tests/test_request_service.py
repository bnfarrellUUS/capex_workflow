import pytest
from decimal import Decimal

from app.extensions import db
from app.services.errors import ServiceError
from app.services import request_service
from tests.factories import make_user, make_division


def test_create_draft_allocates_number_and_prefills_division(app):
    div = make_division()
    user = make_user("req", roles='["REQUESTOR"]')
    user.division_id = div.id
    db.session.commit()
    draft = request_service.create_draft(user)
    assert draft.number.startswith("CX")
    assert draft.status == "DRAFT"
    assert draft.division_id == div.id


def test_update_draft_sets_fields_and_equipment(app):
    user = make_user("req", roles='["REQUESTOR"]')
    draft = request_service.create_draft(user)
    payload = {
        "description": "Forklift",
        "annual_savings": Decimal("10000"),
        "equipment_items": [
            {"units": 2, "condition": "NEW", "type": "Forklift", "make": "Toyota",
             "model": "8FGU25", "cost": Decimal("30000")},
        ],
    }
    updated = request_service.update_draft(draft.id, user, payload)
    assert updated.description == "Forklift"
    assert len(updated.equipment_items) == 1
    assert updated.equipment_items[0].cost == Decimal("30000")


def test_update_draft_owner_only(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    other = make_user("other", roles='["REQUESTOR"]')
    draft = request_service.create_draft(owner)
    with pytest.raises(ServiceError):
        request_service.update_draft(draft.id, other, {"description": "x"})


def test_get_request_access_for_admin(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    admin = make_user("admin", roles='["ADMIN"]')
    draft = request_service.create_draft(owner)
    assert request_service.get_request(draft.id, admin).id == draft.id


def test_get_request_denied_for_stranger(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    stranger = make_user("stranger", roles='["REQUESTOR"]')
    draft = request_service.create_draft(owner)
    with pytest.raises(ServiceError):
        request_service.get_request(draft.id, stranger)


def test_request_out_serializes_money_as_string(app):
    user = make_user("req", roles='["REQUESTOR"]')
    draft = request_service.create_draft(user)
    request_service.update_draft(draft.id, user, {
        "equipment_items": [{"units": 1, "condition": "NEW", "type": "T", "make": "M",
                             "model": "Mo", "cost": Decimal("30000")}]})
    out = request_service.request_out(request_service.get_request(draft.id, user))
    assert out["equipment_items"][0]["cost"] == "30000"
    assert out["status"] == "DRAFT"


def test_request_out_includes_names_and_actions(app):
    from app.services.workflow_service import submit
    from tests.factories import make_user, make_division, set_thresholds, make_draft
    approver = make_user("appr")
    requestor = make_user("req2", roles='["REQUESTOR"]')
    div = make_division(number="900", l1_approver_id=approver.id)
    set_thresholds()
    r = make_draft(requestor.id, div.id, costs=("30000",), number="CX000900")
    submit(r.id, requestor.id)
    out = request_service.request_out(request_service.get_request(r.id, requestor))
    assert out["requestor_name"] == requestor.name
    assert out["assignee_name"] == approver.name
    assert out["division_name"].startswith("900")
    assert any(a["action"] == "SUBMITTED" and a["actor_name"] == requestor.name for a in out["actions"])
