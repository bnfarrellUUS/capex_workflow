from app.extensions import db
from app.models import User, Division, ApprovalThreshold
from app.services.security import verify_password
from seed import seed


def test_seed_creates_admin(app):
    seed(db.session)
    admin = db.session.query(User).filter_by(email="admin@uniteduptime.com").one()
    assert "ADMIN" in admin.roles
    assert verify_password("ChangeMe123!", admin.password_hash)


def test_seed_creates_divisions_and_thresholds(app):
    seed(db.session)
    assert db.session.query(Division).count() >= 1
    assert db.session.query(ApprovalThreshold).count() == 3


def test_seed_is_idempotent(app):
    seed(db.session)
    seed(db.session)
    assert db.session.query(User).filter_by(email="admin@uniteduptime.com").count() == 1
    assert db.session.query(ApprovalThreshold).count() == 3
