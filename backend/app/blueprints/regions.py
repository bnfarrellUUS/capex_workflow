from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.region import RegionCreate, RegionUpdate
from app.services import region_service

bp = Blueprint("regions", __name__, url_prefix="/api/regions")


def region_out(r):
    return {
        "id": r.id, "name": r.name, "active": r.active,
        "vp_approver_ids": [u.id for u in r.vp_approvers],
        "vp_approver_names": [u.name for u in r.vp_approvers],
        "division_count": len(r.divisions),
    }


@bp.get("")
@require_roles("ADMIN")
def list_regions():
    return jsonify([region_out(r) for r in region_service.list_regions()])


@bp.post("")
@require_roles("ADMIN")
def create_region():
    data = RegionCreate(**(request.get_json(silent=True) or {}))
    region = region_service.create_region(**data.model_dump())
    return jsonify(region_out(region)), 201


@bp.patch("/<region_id>")
@require_roles("ADMIN")
def update_region(region_id):
    data = RegionUpdate(**(request.get_json(silent=True) or {}))
    region = region_service.update_region(region_id, **data.model_dump())
    return jsonify(region_out(region))
