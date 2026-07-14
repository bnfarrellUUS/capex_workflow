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


def intended_approvers(level, division, thresholds):
    """The users configured to approve at a level (any one of them may act)."""
    if level == 1:
        return list(division.l1_approvers) if division is not None else []
    match = next((t for t in thresholds if t.level == level), None)
    return list(match.approvers) if match is not None else []


def effective_assignee(user):
    if user is None:
        return None
    return user.delegate if user.delegate_id else user


def eligible_actors(level, division, thresholds):
    """Who may actually act at a level: each configured approver mapped through
    their out-of-office delegate, de-duplicated."""
    seen, out = set(), []
    for approver in intended_approvers(level, division, thresholds):
        actor = effective_assignee(approver)
        if actor is not None and actor.id not in seen:
            seen.add(actor.id)
            out.append(actor)
    return out


def first_assignee(level, division, thresholds):
    actors = eligible_actors(level, division, thresholds)
    return actors[0] if actors else None


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
    l1 = first_assignee(1, req.division, thresholds)
    if l1 is None:
        raise ServiceError("The division has no level-1 approver assigned.")
    req.total_cost = total
    req.required_levels = compute_required_levels(total, thresholds)
    req.current_level = 1
    req.status = "PENDING_L1"
    req.assignee_id = l1.id


def submit(request_id, actor_id):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.status != "DRAFT":
        raise ServiceError("Only drafts can be submitted.")
    if req.requestor_id != actor_id:
        raise ServiceError("Only the requestor can submit this request.", 403)
    _open_workflow(req)
    _add_action(req, actor_id, "SUBMITTED", level=1)
    db.session.commit()
    return req


def _guarded_transition(request_id, expected_level, expected_status, values):
    # Guard on BOTH level and status so terminal transitions (reject, final
    # approve) — which don't change current_level — are still protected against
    # a concurrent second action.
    stmt = (sql_update(CapexRequest)
            .where(CapexRequest.id == request_id,
                   CapexRequest.current_level == expected_level,
                   CapexRequest.status == expected_status)
            .values(**values))
    result = db.session.execute(stmt)
    if result.rowcount != 1:
        raise ServiceError("This request was already actioned by someone else.", 409)


def _require_current_approver(req, actor_id, thresholds):
    if not req.status.startswith("PENDING_L"):
        raise ServiceError("This request is not awaiting a decision.")
    actor_ids = {u.id for u in eligible_actors(req.current_level, req.division, thresholds)}
    if actor_id not in actor_ids:
        raise ServiceError("This request is not assigned to you.", 403)


def _acted_for(req, level, actor_id, thresholds):
    # If the actor is standing in for an approver (their delegate), record whom.
    for approver in intended_approvers(level, req.division, thresholds):
        actor = effective_assignee(approver)
        if actor is not None and actor.id == actor_id and approver.id != actor_id:
            return approver.id
    return None


def approve(request_id, actor_id, comment=None):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    thresholds = threshold_service.list_thresholds()
    _require_current_approver(req, actor_id, thresholds)
    level = req.current_level
    acted_for = _acted_for(req, level, actor_id, thresholds)

    if level >= req.required_levels:
        values = {"status": "APPROVED", "assignee_id": None}
    else:
        nxt = level + 1
        assignee = first_assignee(nxt, req.division, thresholds)
        if assignee is None:
            raise ServiceError(f"No approver configured for level {nxt}.")
        values = {"status": f"PENDING_L{nxt}", "current_level": nxt, "assignee_id": assignee.id}

    _guarded_transition(req.id, level, f"PENDING_L{level}", values)
    _add_action(req, actor_id, "APPROVED", level=level, acted_for_id=acted_for, comment=comment)
    db.session.commit()
    db.session.refresh(req)
    return req


def reject(request_id, actor_id, comment):
    if not comment or not comment.strip():
        raise ServiceError("A comment is required to reject a request.")
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    thresholds = threshold_service.list_thresholds()
    _require_current_approver(req, actor_id, thresholds)
    level = req.current_level
    acted_for = _acted_for(req, level, actor_id, thresholds)
    _guarded_transition(req.id, level, f"PENDING_L{level}", {"status": "REJECTED", "assignee_id": None})
    _add_action(req, actor_id, "REJECTED", level=level, acted_for_id=acted_for, comment=comment)
    db.session.commit()
    db.session.refresh(req)
    return req


_FINANCE_FIELDS = (
    "cost_autos_trucks", "cost_machinery", "cost_improvements",
    "cost_furniture", "cost_permits", "cost_misc",
)


def resubmit(request_id, actor_id):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.status != "REJECTED":
        raise ServiceError("Only rejected requests can be resubmitted.")
    if req.requestor_id != actor_id:
        raise ServiceError("Only the requestor can resubmit.", 403)
    _open_workflow(req)
    _add_action(req, actor_id, "RESUBMITTED", level=1)
    db.session.commit()
    return req


def complete_finance(request_id, actor_id, costs):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    actor = db.session.get(User, actor_id)
    if actor is None or "FINANCE" not in actor.roles_list:
        raise ServiceError("The Finance role is required.", 403)
    if req.status != "APPROVED":
        raise ServiceError("Only approved requests can be completed by Finance.")
    for field in _FINANCE_FIELDS:
        setattr(req, field, costs.get(field))
    req.finance_completed = True
    _add_action(req, actor_id, "FINANCE_COMPLETED")
    db.session.commit()
    return req
