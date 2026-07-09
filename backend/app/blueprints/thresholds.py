from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.threshold import ThresholdsUpdate
from app.serialization import money_str
from app.services import threshold_service

bp = Blueprint("thresholds", __name__, url_prefix="/api/thresholds")


def threshold_out(t):
    return {
        "level": t.level,
        "max_amount": money_str(t.max_amount),
        "approver_ids": [u.id for u in t.approvers],
        "approver_names": [u.name for u in t.approvers],
    }


@bp.get("")
@require_roles("ADMIN")
def get_thresholds():
    return jsonify([threshold_out(t) for t in threshold_service.list_thresholds()])


@bp.put("")
@require_roles("ADMIN")
def put_thresholds():
    data = ThresholdsUpdate(**(request.get_json(silent=True) or {}))
    items = [t.model_dump() for t in data.thresholds]
    rows = threshold_service.set_thresholds(items)
    return jsonify([threshold_out(t) for t in rows])
