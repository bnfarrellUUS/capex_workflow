import logging

from app.extensions import db
from app.models import NotificationLog, User

log = logging.getLogger("capex.notify")


def send_email(recipient, subject, body, request_id=None, type_="INFO"):
    """Best-effort notification. Dev driver logs + records NotificationLog.
    Never raises — a failure must not block a workflow transition."""
    try:
        log.info("EMAIL to=%s subject=%s", recipient, subject)
        db.session.add(NotificationLog(request_id=request_id, recipient=recipient, type=type_))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("notification failed for %s", recipient)


def notify_assignment(req):
    if req.assignee is not None:
        send_email(req.assignee.email, f"{req.number} is waiting for your approval",
                   f"Request {req.number} is assigned to you.", req.id, "ASSIGNED")


def notify_decision(req, approved):
    verb = "approved" if approved else "rejected"
    send_email(req.requestor.email, f"{req.number} was {verb}",
               f"Your request {req.number} was {verb}.", req.id, "DECIDED")


def notify_finance_ready(req):
    users = db.session.query(User).filter(User.active.is_(True)).all()
    for u in users:
        if "FINANCE" in u.roles_list:
            send_email(u.email, f"{req.number} approved — finance section pending",
                       f"Request {req.number} needs the finance cost breakdown.", req.id, "FINANCE_READY")
