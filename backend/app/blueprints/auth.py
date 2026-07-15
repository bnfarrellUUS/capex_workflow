from flask import Blueprint, jsonify, request
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf.csrf import generate_csrf

from app.schemas.auth import SetPasswordIn
from app.services.auth_service import authenticate, set_initial_password

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _user_json(user):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "roles": user.roles_list,
        "division_id": user.division_id,
        "must_change_password": user.must_change_password,
    }


@bp.get("/csrf")
def csrf_token():
    return jsonify(csrfToken=generate_csrf())


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    result = authenticate(data.get("email", ""), data.get("password", ""))
    if not result.ok:
        return jsonify(error=result.error), 401
    # remember=True issues a persistent cookie so email deep links still work
    # after the browser session ends (lifetime: REMEMBER_COOKIE_DURATION).
    login_user(result.user, remember=True)
    return jsonify(_user_json(result.user))


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return jsonify(ok=True)


@bp.get("/me")
@login_required
def me():
    return jsonify(_user_json(current_user))


@bp.post("/set-password")
@login_required
def set_password():
    data = SetPasswordIn(**(request.get_json(silent=True) or {}))
    user = set_initial_password(current_user.id, data.new_password)
    return jsonify(_user_json(user))
