from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.services import report_service

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/summary")
@require_roles("FINANCE", "ADMIN")
def summary_route():
    return jsonify(report_service.summary(request.args.get("year", type=int)))
