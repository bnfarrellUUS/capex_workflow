from app.extensions import db
from app.models import ApprovalThreshold
from app.services.approver_pools import set_pool
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


def set_thresholds(items):
    by_level = {t.level: t for t in list_thresholds()}
    for item in items:
        if item["level"] not in (1, 2, 3):
            raise ServiceError("Invalid threshold level.")
        row = by_level[item["level"]]
        row.max_amount = item["max_amount"]
        set_pool(row, "approvers", item.get("approver_ids"))
    db.session.commit()
    return [by_level[level] for level in (1, 2, 3)]
