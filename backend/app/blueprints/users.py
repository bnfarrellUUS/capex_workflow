from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.user import UserCreate, UserUpdate, PasswordIn
from app.services import user_service

bp = Blueprint("users", __name__, url_prefix="/api/users")


def user_out(u):
    return {
        "id": u.id, "username": u.username, "email": u.email, "name": u.name,
        "roles": u.roles_list, "active": u.active, "division_id": u.division_id,
    }


@bp.get("")
@require_roles("ADMIN")
def list_users():
    return jsonify([user_out(u) for u in user_service.list_users()])


@bp.post("")
@require_roles("ADMIN")
def create_user():
    data = UserCreate(**(request.get_json(silent=True) or {}))
    user = user_service.create_user(**data.model_dump())
    return jsonify(user_out(user)), 201


@bp.patch("/<user_id>")
@require_roles("ADMIN")
def update_user(user_id):
    data = UserUpdate(**(request.get_json(silent=True) or {}))
    user = user_service.update_user(user_id, **data.model_dump())
    return jsonify(user_out(user))


@bp.post("/<user_id>/reset-password")
@require_roles("ADMIN")
def reset_password(user_id):
    data = PasswordIn(**(request.get_json(silent=True) or {}))
    user_service.admin_reset_password(user_id, data.password)
    return jsonify(ok=True)
