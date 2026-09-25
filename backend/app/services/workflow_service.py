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
    """The active users configured to approve at a level (any one may act).

    Inactive users are dropped here, so a deactivated approver is out of every
    pool -- worklists, notifications, who may act, and empty-level skipping all
    follow from this one filter. Deactivating someone must not leave requests
    routed to an account nobody can sign in to."""
    if level == 1:
        pool = division.l1_approvers if division is not None else []
    elif level == 2:
        region = division.region if division is not None else None
        pool = region.vp_approvers if region is not None else []
    else:
        match = next((t for t in thresholds if t.level == level), None)
        pool = match.approvers if match is not None else []
    return [u for u in pool if u.active]


def effective_assignee(user):
    """Who acts for `user`: their out-of-office delegate, unless that delegate
    has been deactivated -- then the approver keeps their own requests."""
    if user is None:
        return None
    if user.delegate_id and user.delegate is not None and user.delegate.active:
        return user.delegate
    return user


def eligible_actors(level, division, thresholds, exclude_id=None):
    """Who may actually act at a level: each configured approver mapped through
    their out-of-office delegate, de-duplicated. `exclude_id` (the requestor)
    is barred in any capacity — as a configured approver or as the delegate
    who would act for one."""
    seen, out = set(), []
    for approver in intended_approvers(level, division, thresholds):
        if exclude_id is not None and approver.id == exclude_id:
            continue
        actor = effective_assignee(approver)
        if actor is None or actor.id in seen:
            continue
        if exclude_id is not None and actor.id == exclude_id:
            continue
        seen.add(actor.id)
        out.append(actor)
    return out


def current_actors(req, thresholds):
    """Who may act on a PENDING request right now: an ADMIN's reassignment
    (if any, and still active) in front, then the current level's pool. Every
    request-level "who can act / see / be notified" question goes through
    here, so a reassigned approver has the same standing everywhere."""
    actors = eligible_actors(req.current_level, req.division, thresholds,
                             exclude_id=req.requestor_id)
    extra = req.reassigned_to
    if extra is None or not extra.active or extra.id == req.requestor_id:
        return actors
    return [extra] + [u for u in actors if u.id != extra.id]


def first_assignee(level, division, thresholds, exclude_id=None):
    actors = eligible_actors(level, division, thresholds, exclude_id=exclude_id)
    return actors[0] if actors else None


def next_pending_level(after_level, division, thresholds, exclude_id=None):
    """The lowest level above `after_level` where someone may act; empty
    levels — unconfigured, or emptied by the requestor exclusion — are
    skipped uniformly. None when nobody is left."""
    for level in (1, 2, 3):
        if level > after_level and eligible_actors(
                level, division, thresholds, exclude_id=exclude_id):
            return level
    return None


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
    if req.budgeted and (req.budget_amount is None or req.budget_amount <= 0):
        raise ServiceError("Enter the budgeted amount for this request.")
    thresholds = threshold_service.list_thresholds()
    first = next_pending_level(0, req.division, thresholds, exclude_id=req.requestor_id)
    if first is None:
        raise ServiceError(
            "No eligible approver was found at any level — requestors cannot "
            "approve their own requests. Check the division's level-1 approvers, "
            "the region's VP list, and the level-3 approvers.")
    req.total_cost = total
    req.required_levels = compute_required_levels(total, thresholds)
    req.current_level = first
    req.status = f"PENDING_L{first}"
    req.reassigned_to_id = None
    req.assignee_id = first_assignee(
        first, req.division, thresholds, exclude_id=req.requestor_id).id


def submit(request_id, actor_id):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.status != "DRAFT":
        raise ServiceError("Only drafts can be submitted.")
    if req.requestor_id != actor_id:
        raise ServiceError("Only the requestor can submit this request.", 403)
    _open_workflow(req)
    _add_action(req, actor_id, "SUBMITTED", level=req.current_level)
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
    actor_ids = {u.id for u in current_actors(req, thresholds)}
    if actor_id not in actor_ids:
        raise ServiceError("This request is not assigned to you.", 403)


def _acted_for(req, level, actor_id, thresholds):
    # If the actor is standing in for an approver (their delegate), record whom.
    for approver in intended_approvers(level, req.division, thresholds):
        if approver.id == req.requestor_id:
            continue
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
        values = {"status": "APPROVED", "assignee_id": None, "reassigned_to_id": None}
    else:
        nxt = next_pending_level(level, req.division, thresholds,
                                 exclude_id=req.requestor_id)
        if nxt is None:
            raise ServiceError(
                "No eligible approver is configured above this level.")
        assignee = first_assignee(nxt, req.division, thresholds,
                                  exclude_id=req.requestor_id)
        values = {"status": f"PENDING_L{nxt}", "current_level": nxt,
                  "assignee_id": assignee.id, "reassigned_to_id": None}

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
    _guarded_transition(req.id, level, f"PENDING_L{level}", {"status": "REJECTED", "assignee_id": None,
                                                        "reassigned_to_id": None})
    _add_action(req, actor_id, "REJECTED", level=level, acted_for_id=acted_for, comment=comment)
    db.session.commit()
    db.session.refresh(req)
    return req


def reassign(request_id, admin_id, user_id, comment=None):
    """ADMIN names a per-request approver for the current level (ADO 5907).

    For a request stuck because every approver at its level was deactivated;
    also usable to route one request to a specific person. The target joins
    the level's approvers in front (so is "assigned to"), is cleared when the
    request leaves the level, must be active, and can never be the requestor.
    Authorization (ADMIN) is the route's job, as for other admin actions."""
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if not req.status.startswith("PENDING_L"):
        raise ServiceError("Only a request awaiting approval can be reassigned.")
    target = db.session.get(User, user_id) if user_id else None
    if target is None or not target.active:
        raise ServiceError("Choose an active user to reassign to.")
    if target.id == req.requestor_id:
        raise ServiceError("A request can't be reassigned to its own requestor.")
    req.reassigned_to_id = target.id
    req.assignee_id = target.id
    note = f"Reassigned to {target.name}"
    if comment and comment.strip():
        note += f": {comment.strip()}"
    _add_action(req, admin_id, "REASSIGNED", level=req.current_level, comment=note)
    db.session.commit()
    db.session.refresh(req)
    return req


def clear_reassignment(request_id, admin_id):
    """ADMIN undoes a reassignment: the request goes back to its level's
    normal pool (ADO 5907's "back into routing"), logged like the reassign."""
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if not req.status.startswith("PENDING_L") or req.reassigned_to_id is None:
        raise ServiceError("This request has no reassignment to clear.")
    req.reassigned_to_id = None
    first = first_assignee(req.current_level, req.division, threshold_service.list_thresholds(),
                           exclude_id=req.requestor_id)
    req.assignee_id = first.id if first else None
    _add_action(req, admin_id, "REASSIGNED", level=req.current_level,
                comment="Returned to normal routing")
    db.session.commit()
    db.session.refresh(req)
    return req


_FINANCE_FIELDS = (
    "cost_autos_trucks", "cost_machinery", "cost_improvements",
    "cost_furniture", "cost_it_computer", "cost_misc",
    "asset_number", "gl_account", "useful_life_years", "useful_life_months",
    "in_service_date",
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
    _add_action(req, actor_id, "RESUBMITTED", level=req.current_level)
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
