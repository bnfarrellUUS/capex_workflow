import logging

from flask import current_app

from app.extensions import db
from app.models import NotificationLog, User

log = logging.getLogger("capex.notify")


def _redirect_note(intended):
    if not (current_app.config.get("EMAIL_ENABLED")
            and current_app.config.get("EMAIL_REDIRECT_TO")):
        return None
    return f"Intended recipient: {intended} (redirected while testing)"


def _emit(intended, subject, html, enabled, request_id, type_):
    """Always record a NotificationLog; deliver via Outlook when enabled."""
    try:
        log.info("EMAIL to=%s subject=%s", intended, subject)
        db.session.add(NotificationLog(request_id=request_id, recipient=intended, type=type_))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("notification log failed for %s", intended)
    if not enabled or not current_app.config.get("EMAIL_ENABLED"):
        return
    redirect_to = current_app.config.get("EMAIL_REDIRECT_TO") or intended
    try:
        from app.services import email_outlook
        email_outlook.send(redirect_to, subject, "", html=html)
    except Exception:
        log.exception("email delivery failed (intended %s)", intended)


def _send_template(intended, type_, req, **extra):
    from app.services import email_template_service as ets
    ctx = ets.context_for(req, **extra)
    out = ets.render(type_, ctx, redirect_note=_redirect_note(intended))
    _emit(intended, out["subject"], out["html"], out["enabled"], req.id, type_)


def notify_assignment(req):
    # Notify every eligible approver at the current level (any one may act).
    from app.services import threshold_service, workflow_service
    actors = workflow_service.eligible_actors(
        req.current_level, req.division, threshold_service.list_thresholds())
    level = f"Level {req.current_level}"
    if req.required_levels:
        level += f" of {req.required_levels}"
    for actor in actors:
        _send_template(actor.email, "ASSIGNED", req, level=level)


def notify_decision(req, approved, comment=None):
    type_ = "APPROVED" if approved else "REJECTED"
    _send_template(req.requestor.email, type_, req, comment=comment or "(no comment)")


def notify_finance_ready(req):
    users = db.session.query(User).filter(User.active.is_(True)).all()
    for u in users:
        if "FINANCE" in u.roles_list:
            _send_template(u.email, "FINANCE_READY", req)


def send_email(recipient, subject, body, request_id=None, type_="INFO"):
    """Direct plain-text send (used for ad-hoc/test messages)."""
    _emit_plain(recipient, subject, body, request_id, type_)


def _emit_plain(intended, subject, body, request_id, type_):
    try:
        log.info("EMAIL to=%s subject=%s", intended, subject)
        db.session.add(NotificationLog(request_id=request_id, recipient=intended, type=type_))
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception("notification log failed for %s", intended)
    if not current_app.config.get("EMAIL_ENABLED"):
        return
    redirect_to = current_app.config.get("EMAIL_REDIRECT_TO") or intended
    note = _redirect_note(intended)
    full = f"{note}\n\n{body}" if note else body
    try:
        from app.services import email_outlook
        email_outlook.send(redirect_to, subject, full)
    except Exception:
        log.exception("email delivery failed (intended %s)", intended)
