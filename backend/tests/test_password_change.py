from app.extensions import db
from app.models import User
from app.services.security import hash_password, verify_password


def _flagged_user(app, email="new@x.com"):
    u = User(email=email, name="New User",
             password_hash=hash_password(app.config["DEFAULT_PASSWORD"]),
             roles='["REQUESTOR"]', must_change_password=True)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, app, email="new@x.com"):
    return client.post("/api/auth/login",
                       json={"email": email, "password": app.config["DEFAULT_PASSWORD"]})


def test_login_reports_flag(client, app):
    _flagged_user(app)
    r = _login(client, app)
    assert r.status_code == 200
    assert r.get_json()["must_change_password"] is True


def test_flagged_user_is_gated_to_403(client, app):
    _flagged_user(app)
    _login(client, app)
    r = client.get("/api/requests")
    assert r.status_code == 403
    assert r.get_json()["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert r.get_json()["error"] == "You must set a new password before continuing."


def test_flagged_user_can_still_use_exempt_endpoints(client, app):
    _flagged_user(app)
    _login(client, app)
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/auth/csrf").status_code == 200


def test_set_password_clears_flag_and_unblocks(client, app):
    u = _flagged_user(app)
    _login(client, app)
    r = client.post("/api/auth/set-password", json={"new_password": "MyOwnPass1"})
    assert r.status_code == 200
    assert r.get_json()["must_change_password"] is False
    db.session.refresh(u)
    assert u.must_change_password is False
    assert verify_password("MyOwnPass1", u.password_hash)
    assert client.get("/api/requests").status_code == 200


def test_set_password_rejects_the_default(client, app):
    _flagged_user(app)
    _login(client, app)
    r = client.post("/api/auth/set-password",
                    json={"new_password": app.config["DEFAULT_PASSWORD"]})
    assert r.status_code == 400


def test_set_password_rejects_short(client, app):
    _flagged_user(app)
    _login(client, app)
    assert client.post("/api/auth/set-password",
                       json={"new_password": "short"}).status_code == 400


def test_set_password_requires_flag(client, app):
    u = _flagged_user(app)
    u.must_change_password = False
    db.session.commit()
    _login(client, app)
    assert client.post("/api/auth/set-password",
                       json={"new_password": "MyOwnPass1"}).status_code == 400


def test_login_as_other_user_is_not_gated(client, app):
    _flagged_user(app)
    _login(client, app)
    other = User(email="other@x.com", name="Other",
                 password_hash=hash_password("OtherPass1"), roles='["REQUESTOR"]')
    db.session.add(other)
    db.session.commit()
    r = client.post("/api/auth/login", json={"email": "other@x.com", "password": "OtherPass1"})
    assert r.status_code == 200
    assert client.get("/api/requests").status_code == 200


def test_logout_stays_available_while_flagged(client, app):
    _flagged_user(app)
    _login(client, app)
    assert client.post("/api/auth/logout").status_code == 200


def test_profile_password_change_clears_flag(client, app):
    u = _flagged_user(app)
    _login(client, app)
    # /api/profile/password is gated while flagged, so clear via set-password
    # first is NOT the point here: flip the flag on directly after a normal
    # change to prove change_password always clears it.
    from app.services import profile_service
    profile_service.change_password(u.id, app.config["DEFAULT_PASSWORD"], "AnotherPass1")
    db.session.refresh(u)
    assert u.must_change_password is False
