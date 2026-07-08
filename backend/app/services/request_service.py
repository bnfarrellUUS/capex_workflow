from app.extensions import db
from app.models import CapexRequest, EquipmentItem
from app.serialization import money_str
from app.services.counter_service import next_request_number
from app.services.errors import ServiceError

_EDITABLE_STATUSES = ("DRAFT", "REJECTED")


def create_draft(requestor):
    req = CapexRequest(
        number=next_request_number(),
        requestor_id=requestor.id,
        division_id=requestor.division_id,
        status="DRAFT",
    )
    db.session.add(req)
    db.session.commit()
    return req


def _can_view(req, viewer):
    if viewer.id in (req.requestor_id, req.assignee_id):
        return True
    roles = viewer.roles_list
    return "ADMIN" in roles or "FINANCE" in roles


def can_view(req, viewer):
    return _can_view(req, viewer)


def get_request(request_id, viewer):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if not _can_view(req, viewer):
        raise ServiceError("You do not have access to this request.", 403)
    return req


def update_draft(request_id, viewer, payload):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.requestor_id != viewer.id:
        raise ServiceError("You can only edit your own requests.", 403)
    if req.status not in _EDITABLE_STATUSES:
        raise ServiceError("This request can no longer be edited.")
    data = dict(payload)
    items = data.pop("equipment_items", None)
    for key, value in data.items():
        setattr(req, key, value)
    if items is not None:
        req.equipment_items = [
            EquipmentItem(units=i["units"], condition=i["condition"], type=i["type"],
                          make=i["make"], model=i["model"], cost=i["cost"])
            for i in items
        ]
    db.session.commit()
    return req


def request_out(req):
    return {
        "id": req.id,
        "number": req.number,
        "status": req.status,
        "requestor_id": req.requestor_id,
        "assignee_id": req.assignee_id,
        "division_id": req.division_id,
        "request_date": req.request_date.isoformat() if req.request_date else None,
        "description": req.description,
        "budgeted": req.budgeted,
        "replacement": req.replacement,
        "health_safety": req.health_safety,
        "revenue_generating": req.revenue_generating,
        "environmental": req.environmental,
        "competitive_bids": req.competitive_bids,
        "lease_recommended": req.lease_recommended,
        "justification": req.justification,
        "effect_on_operations": req.effect_on_operations,
        "asset_life": req.asset_life,
        "irr_after_tax": money_str(req.irr_after_tax),
        "first_year_ebit": money_str(req.first_year_ebit),
        "annual_savings": money_str(req.annual_savings),
        "payback_years": money_str(req.payback_years),
        "npv_savings": money_str(req.npv_savings),
        "cost_autos_trucks": money_str(req.cost_autos_trucks),
        "cost_machinery": money_str(req.cost_machinery),
        "cost_improvements": money_str(req.cost_improvements),
        "cost_furniture": money_str(req.cost_furniture),
        "cost_permits": money_str(req.cost_permits),
        "cost_misc": money_str(req.cost_misc),
        "finance_completed": req.finance_completed,
        "total_cost": money_str(req.total_cost),
        "required_levels": req.required_levels,
        "current_level": req.current_level,
        "equipment_items": [
            {"id": i.id, "units": i.units, "condition": i.condition, "type": i.type,
             "make": i.make, "model": i.model, "cost": money_str(i.cost)}
            for i in req.equipment_items
        ],
        "requestor_name": req.requestor.name if req.requestor else None,
        "assignee_name": req.assignee.name if req.assignee else None,
        "division_name": f"{req.division.number} — {req.division.name}" if req.division else None,
        "actions": [
            {"action": a.action, "level": a.level, "comment": a.comment,
             "created_at": a.created_at.isoformat() if a.created_at else None,
             "actor_name": a.actor.name if a.actor else None}
            for a in sorted(req.actions, key=lambda x: x.created_at or x.id)
        ],
        "attachments": [
            {"id": a.id, "filename": a.filename, "content_type": a.content_type, "size": a.size}
            for a in req.attachments
        ],
    }
