from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.authz import require_roles
from app.schemas.request_sections import HiddenSectionsIn
from app.services import settings_service

bp = Blueprint("request_sections", __name__, url_prefix="/api/request-sections")


@bp.get("")
@login_required
def get_sections():
    # Readable by every signed-in user: the wizard needs it to build its steps.
    return jsonify(hidden=settings_service.get_hidden_sections())


@bp.put("")
@require_roles("ADMIN")
def put_sections():
    payload = HiddenSectionsIn(**(request.get_json(silent=True) or {}))
    return jsonify(hidden=settings_service.set_hidden_sections(payload.hidden))
