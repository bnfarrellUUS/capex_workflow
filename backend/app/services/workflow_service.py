from decimal import Decimal

from sqlalchemy import update as sql_update

from app.extensions import db
from app.models import CapexRequest, ApprovalAction, User
from app.services import threshold_service
from app.services.errors import ServiceError


# ---- pure helpers ----

def compute_required_levels(total_cost, thresholds) -> int:
    for t in sorted(thresholds, key=lambda x: x.level):
        if t.max_amount is None or total_cost <= t.max_amount:
            return t.level
    return max(t.level for t in thresholds)


def intended_approver(level, division, thresholds):
    if level == 1:
        return division.l1_approver if division is not None else None
    match = next((t for t in thresholds if t.level == level), None)
    return match.approver if match is not None else None


def effective_assignee(user):
    if user is None:
        return None
    return user.delegate if user.delegate_id else user


def resolve_assignee(level, division, thresholds):
    return effective_assignee(intended_approver(level, division, thresholds))


# ---- transactional actions ----

def _add_action(req, actor_id, action, level=None, acted_for_id=None, comment=None):
    db.session.add(ApprovalAction(
        request_id=req.id, actor_id=actor_id, action=action,
        level=level, acted_for_id=acted_for_id, comment=comment,
    ))


def _open_workflow(req):
    total = sum((i.cost for i in req.equipment_items), Decimal(0))
    if not req.equipment_items or total <= 0:
        raise ServiceError("Add at least one equipment line item with a cost.")
    if req.division is None:
        raise ServiceError("A division is required.")
    thresholds = threshold_service.list_thresholds()
    l1 = intended_approver(1, req.division, thresholds)
    if l1 is None:
        raise ServiceError("The division has no level-1 approver assigned.")
    req.total_cost = total
    req.required_levels = compute_required_levels(total, thresholds)
    req.current_level = 1
    req.status = "PENDING_L1"
    req.assignee_id = effective_assignee(l1).id


def submit(request_id, actor_id):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.status != "DRAFT":
        raise ServiceError("Only drafts can be submitted.")
    _open_workflow(req)
    _add_action(req, actor_id, "SUBMITTED", level=1)
    db.session.commit()
    return req
