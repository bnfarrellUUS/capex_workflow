from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.division import DivisionCreate, DivisionUpdate
from app.services import division_service

bp = Blueprint("divisions", __name__, url_prefix="/api/divisions")


def division_out(d):
    return {
        "id": d.id, "number": d.number, "name": d.name,
        "active": d.active,
        "l1_approver_ids": [u.id for u in d.l1_approvers],
        "l1_approver_names": [u.name for u in d.l1_approvers],
    }


@bp.get("")
@require_roles("ADMIN")
def list_divisions():
    return jsonify([division_out(d) for d in division_service.list_divisions()])


@bp.post("")
@require_roles("ADMIN")
def create_division():
    data = DivisionCreate(**(request.get_json(silent=True) or {}))
    div = division_service.create_division(**data.model_dump())
    return jsonify(division_out(div)), 201


@bp.patch("/<division_id>")
@require_roles("ADMIN")
def update_division(division_id):
    data = DivisionUpdate(**(request.get_json(silent=True) or {}))
    div = division_service.update_division(division_id, **data.model_dump())
    return jsonify(division_out(div))
