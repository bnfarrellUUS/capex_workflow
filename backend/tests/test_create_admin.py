import pytest

from app.extensions import db
from app.models import User
from app.services.security import verify_password
from create_admin import create_admin


def test_creates_an_active_admin_who_need_not_change_password(app):
    user = create_admin(db.session, " Jane.Doe@UnitedUptime.com ", " Jane Doe ",
                        "a-long-enough-pw")
    assert user.email == "jane.doe@uniteduptime.com"
    assert user.name == "Jane Doe"
    assert user.roles_list == ["ADMIN"]
    assert user.active
    assert not user.must_change_password
    assert verify_password("a-long-enough-pw", user.password_hash)
    assert db.session.query(User).count() == 1


def test_refuses_a_short_password(app):
    with pytest.raises(ValueError, match="12"):
        create_admin(db.session, "a@uniteduptime.com", "A", "short-pw")
    assert db.session.query(User).count() == 0


def test_refuses_an_existing_email(app):
    create_admin(db.session, "a@uniteduptime.com", "A", "a-long-enough-pw")
    with pytest.raises(ValueError, match="already exists"):
        create_admin(db.session, "A@uniteduptime.com", "A", "a-long-enough-pw")
