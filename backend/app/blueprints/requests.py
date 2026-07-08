from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.schemas.request import RequestDraft
from app.services import request_service

bp = Blueprint("requests", __name__, url_prefix="/api/requests")


@bp.post("")
@login_required
def create_request():
    req = request_service.create_draft(current_user)
    return jsonify(request_service.request_out(req)), 201


@bp.get("/<request_id>")
@login_required
def get_request(request_id):
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))


@bp.patch("/<request_id>")
@login_required
def update_request(request_id):
    data = RequestDraft(**(request.get_json(silent=True) or {}))
    req = request_service.update_draft(request_id, current_user, data.model_dump(exclude_unset=True))
    return jsonify(request_service.request_out(req))
