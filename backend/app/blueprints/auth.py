from flask import (Blueprint, jsonify, request, redirect, session, current_app,
                   abort)
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf.csrf import generate_csrf

from app.schemas.auth import SetPasswordIn
from app.services import sso_service
from app.services.auth_service import authenticate, set_initial_password

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _user_json(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "roles": user.roles_list,
        "division_id": user.division_id,
        "must_change_password": user.must_change_password,
        # How this session signed in. The frontend uses it to skip the
        # forced-password-change redirect for SSO users, who have no password
        # to change (app/__init__.py does the same server-side).
        "auth_method": session.get("auth_method", "password"),
    }


@bp.get("/csrf")
def csrf_token():
    return jsonify(csrfToken=generate_csrf())


@bp.post("/login")
def login():
    # FIRST line, before the body, the database or bcrypt: when SSO is
    # configured it is the only way in. Cheap, unreachable-around, and a
    # credential-stuffing run costs one string comparison instead of a hash.
    if sso_service.sso_config() is not None:
        return jsonify(error="Password sign-in is disabled. Use Sign in with Microsoft."), 403
    data = request.get_json(silent=True) or {}
    result = authenticate(data.get("email", ""), data.get("password", ""))
    if not result.ok:
        return jsonify(error=result.error), 401
    # remember=True issues a persistent cookie so email deep links still work
    # after the browser session ends (lifetime: REMEMBER_COOKIE_DURATION).
    login_user(result.user, remember=True)
    session["auth_method"] = "password"
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


@bp.get("/config")
def auth_config():
    """Unauthenticated: tells the login screen whether to offer SSO.

    This has to exist and has to be open -- /api/auth/me returns 401 before
    login, so the login screen has no other way to learn which form to draw. It
    leaks one boolean, which is visible from the login page anyway.
    """
    return jsonify(ok=True, sso_enabled=sso_service.sso_config() is not None)


@bp.get("/sso/login")
def sso_login():
    cfg = sso_service.sso_config()
    if cfg is None:
        abort(404)  # not 403: with SSO off this entry point does not exist
    try:
        flow = sso_service.build_auth_flow(cfg)
    except Exception as e:
        current_app.logger.warning("SSO could not start: %s", e)
        return redirect("/login?sso_error=auth_failed")
    session["sso_flow"] = flow
    session["sso_next"] = sso_service.safe_next_path(request.args.get("next"))
    return redirect(flow["auth_uri"])


@bp.get("/sso/callback")
def sso_callback():
    cfg = sso_service.sso_config()
    if cfg is None:
        abort(404)
    # pop, not get: a flow is single-use, and leaving it in the session invites
    # replay of the callback URL.
    flow = session.pop("sso_flow", None)
    nxt = session.pop("sso_next", "") or "/"
    try:
        if not flow:
            # Someone hitting /callback directly, or after the session expired.
            raise sso_service.SsoError("auth_failed", "no flow in session")
        claims = sso_service.redeem(cfg, flow, request.args)
        user = sso_service.resolve_user(cfg, claims)
    except sso_service.SsoError as e:
        # The code is from a fixed vocabulary; the detail is logged, never
        # returned. Redirect rather than JSON: this is a top-level navigation,
        # and a JSON body renders as a blank page with text on it. /login
        # rather than / because / is inside ProtectedLayout, which would bounce
        # to /login?next=/ and discard the code.
        current_app.logger.warning("SSO refused (%s): %s", e.code, e)
        return redirect(f"/login?sso_error={e.code}")
    session.permanent = True
    # remember=False, unlike the password path: centralised revocation is much
    # of the point of SSO, and a 30-day cookie would outlive an Entra removal.
    login_user(user, remember=False)
    session["auth_method"] = "sso"
    return redirect(nxt)
