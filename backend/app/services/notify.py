import logging

from flask import current_app

from app.extensions import db
from app.models import NotificationLog, User

log = logging.getLogger("capex.notify")


def send_email(recipient, subject, body, request_id=None, type_="INFO"):
    """Best-effort notification. Always logs + records NotificationLog, and (when
    EMAIL_ENABLED) delivers the message through the configured backend.
    Never raises — a failure must not block a workflow transition."""
    try:
        log.info("EMAIL to=%s subject=%s", recipient, subject)
        db.session.add(NotificationLog(request_id=request_id, recipient=recipient, type=type_))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("notification log failed for %s", recipient)
    _deliver(recipient, subject, body)


def _deliver(recipient, subject, body):
    """Send the message via Outlook when email is enabled. While running locally
    every message is redirected to EMAIL_REDIRECT_TO with the intended recipient
    noted in the body. Delivery failures are logged, never raised."""
    if not current_app.config.get("EMAIL_ENABLED"):
        return
    redirect_to = current_app.config.get("EMAIL_REDIRECT_TO") or recipient
    try:
        from app.services import email_outlook
        full_body = f"[Intended recipient: {recipient}]\n\n{body}"
        email_outlook.send(redirect_to, subject, full_body)
    except Exception:
        log.exception("email delivery failed (intended %s)", recipient)


def _request_url(req):
    base = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
    return f"{base}/requests/{req.id}"


def _money(value):
    return f"${value:,.2f}" if value is not None else "—"


def _request_facts(req):
    division = f"{req.division.number} — {req.division.name}" if req.division else "—"
    requestor = req.requestor.name if req.requestor else "—"
    return (f"Requested by: {requestor}\n"
            f"Division:     {division}\n"
            f"Total cost:   {_money(req.total_cost)}")


def notify_assignment(req):
    # Notify every eligible approver at the current level (any one may act).
    from app.services import threshold_service, workflow_service
    actors = workflow_service.eligible_actors(
        req.current_level, req.division, threshold_service.list_thresholds())
    level = f"Level {req.current_level}"
    if req.required_levels:
        level += f" of {req.required_levels}"
    subject = f"Action needed: {req.number} awaiting your {level} approval"
    body = (
        f"Request {req.number} needs your {level} approval.\n\n"
        f"{_request_facts(req)}\n\n"
        f"Review and approve:\n{_request_url(req)}\n"
    )
    for actor in actors:
        send_email(actor.email, subject, body, req.id, "ASSIGNED")


def notify_decision(req, approved):
    verb = "approved" if approved else "rejected"
    if approved:
        tail = "It has been fully approved and is now with Finance for completion."
    else:
        tail = ("Open the request to see the reviewer's comment; you can edit and "
                "resubmit it.")
    body = (
        f"Your request {req.number} ({_money(req.total_cost)}) was {verb}.\n"
        f"{tail}\n\n"
        f"View the request:\n{_request_url(req)}\n"
    )
    send_email(req.requestor.email, f"{req.number} was {verb}", body, req.id, "DECIDED")


def notify_finance_ready(req):
    subject = f"{req.number} approved — finance section pending"
    body = (
        f"Request {req.number} ({_money(req.total_cost)}) has been fully approved "
        f"and needs the finance cost breakdown.\n\n"
        f"{_request_facts(req)}\n\n"
        f"Complete the finance section:\n{_request_url(req)}\n"
    )
    users = db.session.query(User).filter(User.active.is_(True)).all()
    for u in users:
        if "FINANCE" in u.roles_list:
            send_email(u.email, subject, body, req.id, "FINANCE_READY")
