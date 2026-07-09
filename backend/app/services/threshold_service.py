from app.extensions import db
from app.models import ApprovalThreshold, User
from app.services.errors import ServiceError


def list_thresholds():
    existing = {t.level: t for t in db.session.query(ApprovalThreshold).all()}
    for level in (1, 2, 3):
        if level not in existing:
            t = ApprovalThreshold(level=level, max_amount=None)
            db.session.add(t)
            existing[level] = t
    db.session.commit()
    return [existing[level] for level in (1, 2, 3)]


def _users(ids):
    ids = [i for i in (ids or []) if i]
    return db.session.query(User).filter(User.id.in_(ids)).all() if ids else []


def set_thresholds(items):
    by_level = {t.level: t for t in list_thresholds()}
    for item in items:
        if item["level"] not in (1, 2, 3):
            raise ServiceError("Invalid threshold level.")
        row = by_level[item["level"]]
        row.max_amount = item["max_amount"]
        row.approvers = _users(item.get("approver_ids"))
    db.session.commit()
    return [by_level[level] for level in (1, 2, 3)]
