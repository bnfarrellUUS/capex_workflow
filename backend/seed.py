from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import User, Division, ApprovalThreshold
from app.services.security import hash_password


def _get_or_create(session, model, defaults=None, **key):
    obj = session.query(model).filter_by(**key).one_or_none()
    if obj is not None:
        return obj
    obj = model(**key, **(defaults or {}))
    session.add(obj)
    session.flush()
    return obj


def seed(session) -> None:
    _get_or_create(
        session, User,
        email="admin@uniteduptime.com",
        defaults={
            "name": "Administrator",
            "password_hash": hash_password("ChangeMe123!"),
            "roles": '["ADMIN","REQUESTOR","APPROVER","FINANCE"]',
        },
    )
    _get_or_create(session, Division, number="100", defaults={"name": "Field Services"})
    _get_or_create(session, Division, number="200", defaults={"name": "Corporate"})
    _get_or_create(session, ApprovalThreshold, level=1, defaults={"max_amount": Decimal("50000")})
    _get_or_create(session, ApprovalThreshold, level=2, defaults={"max_amount": Decimal("250000")})
    _get_or_create(session, ApprovalThreshold, level=3, defaults={"max_amount": None})
    session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed(db.session)
        print("Seed complete.")
