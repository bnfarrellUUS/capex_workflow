import logging

from flask import current_app

from app.extensions import db
from app.models import NotificationLog, User
from app.services import settings_service

log = logging.getLogger("capex.notify")


def _delivery(intended):
    """Resolve (recipient, redirect_note) from the current email mode.

    Test mode redirects everything to the configured test recipient and adds a
    banner naming the intended recipient; Live mode sends to the real one.
    """
    settings = settings_service.get_email_settings()
    if settings["mode"] == "test":
        to = settings["test_recipient"] or intended
        note = f"Intended recipient: {intended} (redirected while testing)"
        return to, note
    return intended, None


def _redirect_note(intended):
    return _delivery(intended)[1]


def _emit(intended, subject, html, enabled, request_id, type_, attachments=None):
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
    redirect_to = _delivery(intended)[0]
    try:
        from app.services import email_outlook
        email_outlook.send(redirect_to, subject, "", html=html, attachments=attachments)
    except Exception:
        log.exception("email delivery failed (intended %s)", intended)


def _send_template(intended, type_, req, attachments=None, **extra):
    from app.services import email_template_service as ets
    ctx = ets.context_for(req, **extra)
    out = ets.render(type_, ctx, redirect_note=_redirect_note(intended))
    _emit(intended, out["subject"], out["html"], out["enabled"], req.id, type_,
          attachments=attachments)


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


def notify_finance_complete(req):
    """Final record email: the requestor keeps a PDF of the finished request."""
    from app.services import pdf_service, settings_service
    pdf = pdf_service.build_request_pdf(req, settings_service.get_hidden_sections())
    _send_template(req.requestor.email, "FINANCE_COMPLETE", req,
                   attachments=[(pdf_service.pdf_filename(req), pdf)])


def notify_comment(req, comment):
    """Tell the other side of the conversation. Never the author."""
    from app.services import threshold_service, workflow_service
    if comment.author_id == req.requestor_id:
        # Whoever is holding the request answers the requestor.
        if req.status.startswith("PENDING_L"):
            recipients = workflow_service.eligible_actors(
                req.current_level, req.division, threshold_service.list_thresholds())
        elif req.status == "APPROVED":
            recipients = [u for u in db.session.query(User)
                          .filter(User.active.is_(True)).all()
                          if "FINANCE" in u.roles_list]
        else:
            recipients = []          # DRAFT / REJECTED: nobody is waiting on it
        emails = [u.email for u in recipients]
    else:
        emails = [req.requestor.email] if req.requestor else []

    author = comment.author.name if comment.author else "Someone"
    author_email = comment.author.email if comment.author else None
    seen = set()
    for email in emails:
        if email == author_email or email in seen:
            continue
        seen.add(email)
        _send_template(email, "COMMENT", req, author=author, comment=comment.body)


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
    redirect_to, note = _delivery(intended)
    full = f"{note}\n\n{body}" if note else body
    try:
        from app.services import email_outlook
        email_outlook.send(redirect_to, subject, full)
    except Exception:
        log.exception("email delivery failed (intended %s)", intended)
