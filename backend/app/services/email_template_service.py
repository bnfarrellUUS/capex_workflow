from flask import current_app

from app.extensions import db
from app.models import EmailTemplate
from app.services import email_frame
from app.services.errors import ServiceError

TYPES = ("ASSIGNED", "APPROVED", "REJECTED", "FINANCE_READY")

NAMES = {
    "ASSIGNED": "Approval needed",
    "APPROVED": "Request approved",
    "REJECTED": "Request rejected",
    "FINANCE_READY": "Finance section pending",
}

_COMMON = [
    {"token": "{number}", "description": "Request number (e.g. CX000042)"},
    {"token": "{requestor}", "description": "Name of the person who submitted"},
    {"token": "{division}", "description": "Division, e.g. 12 — Field Services"},
    {"token": "{total_cost}", "description": "Total cost, e.g. $182,400.00"},
    {"token": "{link}", "description": "Deep link to the request in the app"},
]
TOKENS = {
    "ASSIGNED": _COMMON + [{"token": "{level}", "description": "Level awaiting you, e.g. Level 2 of 3"}],
    "APPROVED": _COMMON,
    "REJECTED": _COMMON + [{"token": "{comment}", "description": "Reviewer's rejection comment"}],
    "FINANCE_READY": _COMMON,
}

_BTN = (
    'style="display:inline-block;background:#2563EB;color:#ffffff;'
    'text-decoration:none;padding:10px 18px;border-radius:8px;font-weight:bold;"'
)
_FACTS = (
    '<table style="margin:16px 0;border-collapse:collapse;font-size:14px;">'
    "<tr><td style=\"padding:2px 12px 2px 0;color:#64748B;\">Requested by</td>"
    "<td><strong>{requestor}</strong></td></tr>"
    "<tr><td style=\"padding:2px 12px 2px 0;color:#64748B;\">Division</td>"
    "<td>{division}</td></tr>"
    "<tr><td style=\"padding:2px 12px 2px 0;color:#64748B;\">Total cost</td>"
    "<td>{total_cost}</td></tr></table>"
)

DEFAULTS = {
    "ASSIGNED": {
        "subject": "Action needed: {number} awaiting your {level} approval",
        "body_html": (
            "<p>Request <strong>{number}</strong> needs your <strong>{level}</strong> "
            "approval.</p>" + _FACTS +
            f'<p><a href="{{link}}" {_BTN}>Review &amp; approve</a></p>'
        ),
    },
    "APPROVED": {
        "subject": "{number} was approved",
        "body_html": (
            "<p>Your request <strong>{number}</strong> ({total_cost}) was "
            "<strong>approved</strong>. It is now with Finance for completion.</p>"
            f'<p><a href="{{link}}" {_BTN}>View the request</a></p>'
        ),
    },
    "REJECTED": {
        "subject": "{number} was rejected",
        "body_html": (
            "<p>Your request <strong>{number}</strong> ({total_cost}) was "
            "<strong>rejected</strong>.</p>"
            '<p style="background:#FEF2F2;border-left:3px solid #B91C1C;padding:8px 12px;">'
            "Reviewer's comment: {comment}</p>"
            "<p>You can edit and resubmit it.</p>"
            f'<p><a href="{{link}}" {_BTN}>Open the request</a></p>'
        ),
    },
    "FINANCE_READY": {
        "subject": "{number} approved — finance section pending",
        "body_html": (
            "<p>Request <strong>{number}</strong> ({total_cost}) has been fully "
            "approved and needs the finance cost breakdown.</p>" + _FACTS +
            f'<p><a href="{{link}}" {_BTN}>Complete the finance section</a></p>'
        ),
    },
}


def _require_type(type_):
    if type_ not in TYPES:
        raise ServiceError("Unknown email template.", 404)


def get(type_):
    _require_type(type_)
    row = db.session.get(EmailTemplate, type_)
    shipped = DEFAULTS[type_]
    if row is None:
        return {
            "type": type_, "name": NAMES[type_],
            "subject": shipped["subject"], "body_html": shipped["body_html"],
            "enabled": True,
            "default_subject": shipped["subject"],
            "default_body_html": shipped["body_html"],
            "is_custom": False,
        }
    return {
        "type": type_, "name": NAMES[type_],
        "subject": row.subject, "body_html": row.body_html, "enabled": row.enabled,
        "default_subject": row.default_subject,
        "default_body_html": row.default_body_html,
        "is_custom": True,
    }


def _row_or_seed(type_):
    row = db.session.get(EmailTemplate, type_)
    if row is None:
        shipped = DEFAULTS[type_]
        row = EmailTemplate(
            type=type_, subject=shipped["subject"], body_html=shipped["body_html"],
            enabled=True, default_subject=shipped["subject"],
            default_body_html=shipped["body_html"])
        db.session.add(row)
    return row


def save(type_, subject, body_html, enabled):
    _require_type(type_)
    row = _row_or_seed(type_)
    row.subject, row.body_html, row.enabled = subject, body_html, enabled
    db.session.commit()
    return get(type_)


def save_as_default(type_):
    _require_type(type_)
    row = _row_or_seed(type_)
    row.default_subject, row.default_body_html = row.subject, row.body_html
    db.session.commit()
    return get(type_)


def reset(type_):
    _require_type(type_)
    row = db.session.get(EmailTemplate, type_)
    if row is None:
        return get(type_)
    row.subject, row.body_html = row.default_subject, row.default_body_html
    db.session.commit()
    return get(type_)


def _substitute(text, context):
    for key, value in context.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def preview(type_, subject, body_html):
    _require_type(type_)
    ctx = sample_context(type_)
    return {
        "subject": _substitute(subject, ctx),
        "html": email_frame.wrap(_substitute(body_html, ctx)),
    }


def render(type_, context, *, redirect_note=None):
    tmpl = get(type_)
    subject = _substitute(tmpl["subject"], context)
    body = _substitute(tmpl["body_html"], context)
    return {
        "subject": subject,
        "html": email_frame.wrap(body, redirect_note=redirect_note),
        "enabled": tmpl["enabled"],
    }


def context_for(req, **extra):
    division = f"{req.division.number} — {req.division.name}" if req.division else "—"
    base = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
    ctx = {
        "number": req.number,
        "requestor": req.requestor.name if req.requestor else "—",
        "division": division,
        "total_cost": f"${req.total_cost:,.2f}" if req.total_cost is not None else "—",
        "link": f"{base}/requests/{req.id}",
    }
    ctx.update(extra)
    return ctx


def sample_context(type_):
    ctx = {
        "number": "CX000042", "requestor": "Dana Ruiz",
        "division": "12 — Field Services", "total_cost": "$182,400.00",
        "link": "http://localhost:5000/requests/sample",
        "level": "Level 2 of 3", "comment": "Please attach the competitive bids.",
    }
    return ctx
