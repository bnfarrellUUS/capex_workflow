"""An admin password reset signs the user out everywhere.

The Flask-Login id is "<user id>:<session_version>", so it is baked into both
the session cookie and the 30-day remember-me cookie; the reset bumps the
version and every cookie issued before it stops loading.
"""

from flask import g

from app.extensions import db
from app.models import User
from tests.factories import make_user


def _me(c):
    """GET /api/auth/me as a fresh request. The `app` fixture holds one app
    context for the whole test, so Flask-Login's per-request cache on `g`
    (and the session's identity map) would otherwise leak between clients;
    in production each request gets its own."""
    g.pop("_login_user", None)
    db.session.expire_all()
    return c.get("/api/auth/me").status_code


def _signed_in(app, key):
    c = app.test_client()
    assert c.post("/api/auth/login", json={"email": f"{key}@x.com", "password": "secret123"}).status_code == 200
    assert _me(c) == 200
    return c


def _reset(app, user_id):
    admin = _signed_in(app, "admin")
    assert admin.post(f"/api/users/{user_id}/reset-password").status_code == 200


def test_reset_ends_the_users_existing_session(app):
    make_user("admin", roles='["ADMIN"]')
    victim = make_user("victim")
    victim_client = _signed_in(app, "victim")

    _reset(app, victim.id)

    assert _me(victim_client) == 401


def test_reset_also_voids_the_remember_me_cookie(app):
    make_user("admin", roles='["ADMIN"]')
    victim = make_user("victim")
    victim_client = _signed_in(app, "victim")
    # A browser restart: the session cookie is gone, only remember_token is left.
    victim_client.delete_cookie("session")
    assert _me(victim_client) == 200   # remember-me works

    victim_client.delete_cookie("session")
    _reset(app, victim.id)

    assert _me(victim_client) == 401


def test_signing_in_again_after_the_reset_works(app):
    make_user("admin", roles='["ADMIN"]')
    victim = make_user("victim")
    _reset(app, victim.id)
    c = app.test_client()
    login = c.post("/api/auth/login", json={"email": "victim@x.com",
                                            "password": app.config["DEFAULT_PASSWORD"]})
    assert login.status_code == 200
    assert _me(c) == 200


def test_other_users_stay_signed_in(app):
    make_user("admin", roles='["ADMIN"]')
    victim = make_user("victim")
    make_user("bystander")
    bystander_client = _signed_in(app, "bystander")
    _reset(app, victim.id)
    assert _me(bystander_client) == 200


def test_a_session_from_before_versioning_still_loads(app):
    # Cookies issued before this change hold the bare user id. They keep
    # working until the user's first reset, so deploying signs no one out.
    user = make_user("old")
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = user.id
        s["_fresh"] = True
    assert _me(c) == 200

    user.session_version = 1
    db.session.commit()
    assert _me(c) == 401


def test_a_malformed_id_is_anonymous(app):
    user = make_user("odd")
    c = app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = f"{user.id}:not-a-number"
    assert _me(c) == 401
