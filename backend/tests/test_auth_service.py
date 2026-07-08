from app.extensions import db
from app.models import User
from app.services.security import hash_password
from app.services.auth_service import authenticate, MAX_FAILED_LOGINS


def _user(**kw):
    defaults = dict(
        username="jdoe", email="j@x.com", name="J",
        password_hash=hash_password("secret123"), active=True,
    )
    defaults.update(kw)
    u = User(**defaults)
    db.session.add(u)
    db.session.commit()
    return u


def test_authenticate_success(app):
    _user()
    res = authenticate("jdoe", "secret123")
    assert res.ok and res.user.username == "jdoe"


def test_authenticate_is_case_insensitive(app):
    _user(username="jdoe")
    assert authenticate("JDoe", "secret123").ok


def test_wrong_password_increments_counter(app):
    _user()
    assert not authenticate("jdoe", "nope").ok
    u = db.session.query(User).filter_by(username="jdoe").one()
    assert u.failed_logins == 1


def test_lockout_after_max_failures(app):
    _user()
    for _ in range(MAX_FAILED_LOGINS):
        authenticate("jdoe", "nope")
    u = db.session.query(User).filter_by(username="jdoe").one()
    assert u.locked_until is not None
    # Correct password is still rejected while locked.
    assert not authenticate("jdoe", "secret123").ok


def test_unknown_user_fails(app):
    assert not authenticate("ghost", "whatever").ok


def test_inactive_user_fails(app):
    _user(active=False)
    assert not authenticate("jdoe", "secret123").ok


def test_success_resets_counter(app):
    _user(failed_logins=3)
    assert authenticate("jdoe", "secret123").ok
    u = db.session.query(User).filter_by(username="jdoe").one()
    assert u.failed_logins == 0
