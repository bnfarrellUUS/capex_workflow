from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.schemas.request import RequestDraft, FinanceIn
from app.services import request_service, workflow_service, notify

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


@bp.post("/<request_id>/submit")
@login_required
def submit_request(request_id):
    req = workflow_service.submit(request_id, current_user.id)
    notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/approve")
@login_required
def approve_request(request_id):
    comment = (request.get_json(silent=True) or {}).get("comment")
    req = workflow_service.approve(request_id, current_user.id, comment)
    if req.status == "APPROVED":
        notify.notify_decision(req, True)
        notify.notify_finance_ready(req)
    else:
        notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/reject")
@login_required
def reject_request(request_id):
    comment = (request.get_json(silent=True) or {}).get("comment", "")
    req = workflow_service.reject(request_id, current_user.id, comment)
    notify.notify_decision(req, False)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/resubmit")
@login_required
def resubmit_request(request_id):
    req = workflow_service.resubmit(request_id, current_user.id)
    notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/finance")
@login_required
def finance_request(request_id):
    costs = FinanceIn(**(request.get_json(silent=True) or {})).model_dump()
    req = workflow_service.complete_finance(request_id, current_user.id, costs)
    return jsonify(request_service.request_out(req))
