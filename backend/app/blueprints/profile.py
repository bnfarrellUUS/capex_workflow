from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.schemas.profile import DelegateIn, ChangePasswordIn
from app.services import profile_service

bp = Blueprint("profile", __name__, url_prefix="/api/profile")


def profile_out(u):
    return {
        "id": u.id, "username": u.username, "name": u.name, "email": u.email,
        "roles": u.roles_list, "division_id": u.division_id, "delegate_id": u.delegate_id,
    }


@bp.get("")
@login_required
def get_profile():
    return jsonify(profile_out(current_user))


@bp.get("/delegate-options")
@login_required
def delegate_options():
    users = profile_service.delegate_options(current_user.id)
    return jsonify([{"id": u.id, "name": u.name} for u in users])


@bp.patch("")
@login_required
def set_delegate():
    data = DelegateIn(**(request.get_json(silent=True) or {}))
    user = profile_service.set_delegate(current_user.id, data.delegate_id)
    return jsonify(profile_out(user))


@bp.post("/password")
@login_required
def change_password():
    data = ChangePasswordIn(**(request.get_json(silent=True) or {}))
    profile_service.change_password(current_user.id, data.current_password, data.new_password)
    return jsonify(ok=True)
