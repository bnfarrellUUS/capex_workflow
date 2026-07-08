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
