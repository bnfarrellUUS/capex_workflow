from app.extensions import db
from app.models import User, Division, ApprovalThreshold, Region
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


def test_seed_creates_central_region(app):
    seed(db.session)
    admin = db.session.query(User).filter_by(email="admin@uniteduptime.com").one()
    region = db.session.query(Region).filter_by(name="Central").one()
    assert admin in region.vp_approvers
    div_100 = db.session.query(Division).filter_by(number="100").one()
    div_200 = db.session.query(Division).filter_by(number="200").one()
    assert div_100.region_id == region.id
    assert div_200.region_id == region.id


# --- the CLI guard: the seed's admin password is public (it is in the repo) ---

import pytest

from seed import check_seed_target


def test_seed_target_allows_sqlite():
    check_seed_target("sqlite:///capex_dev.db", allow_non_sqlite=False)


def test_seed_target_refuses_azure_sql_without_the_flag():
    url = "mssql+pyodbc:///?odbc_connect=Pwd%3Dsecret"
    with pytest.raises(SystemExit) as exc:
        check_seed_target(url, allow_non_sqlite=False)
    message = str(exc.value)
    assert "--allow-non-sqlite" in message
    assert "secret" not in message  # never echo the connection string


def test_seed_target_allows_azure_sql_with_the_flag():
    check_seed_target("mssql+pyodbc:///?odbc_connect=x", allow_non_sqlite=True)
