import html

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

# Outlook's Word engine ignores padding on <a>, so the button's size/shape must
# come from the <td> (bgcolor + padding); border-radius degrades to square there.
_F = "Arial,Helvetica,sans-serif"


def _button(label):
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" '
        'style="margin:20px 0 8px;"><tr>'
        '<td bgcolor="#2563EB" style="padding:12px 22px;border-radius:8px;">'
        f'<a href="{{link}}" style="font:bold 15px {_F};color:#ffffff;'
        f'text-decoration:none;">{label}</a>'
        "</td></tr></table>"
    )


def _fact_row(label, value):
    # Every <td> carries its own font — Outlook resets fonts per cell.
    return (
        f'<tr><td width="110" style="padding:3px 12px 3px 0;font:14px {_F};'
        f'color:#64748B;">{label}</td>'
        f'<td style="padding:3px 0;font:14px {_F};color:#0B1B2B;">{value}</td></tr>'
    )


_FACTS = (
    '<table role="presentation" cellpadding="0" cellspacing="0" '
    'style="margin:16px 0;">'
    + _fact_row("Requested by", "<strong>{requestor}</strong>")
    + _fact_row("Division", "{division}")
    + _fact_row("Total cost", "{total_cost}")
    + "</table>"
)

DEFAULTS = {
    "ASSIGNED": {
        "subject": "Action needed: {number} awaiting your {level} approval",
        "body_html": (
            "<p>Request <strong>{number}</strong> needs your <strong>{level}</strong> "
            "approval.</p>" + _FACTS + _button("Review &amp; approve")
        ),
    },
    "APPROVED": {
        "subject": "{number} was approved",
        "body_html": (
            "<p>Your request <strong>{number}</strong> ({total_cost}) was "
            "<strong>approved</strong>. It is now with Finance for completion.</p>"
            + _button("View the request")
        ),
    },
    "REJECTED": {
        "subject": "{number} was rejected",
        "body_html": (
            "<p>Your request <strong>{number}</strong> ({total_cost}) was "
            "<strong>rejected</strong>.</p>"
            '<table role="presentation" cellpadding="0" cellspacing="0" '
            'style="margin:12px 0;"><tr>'
            '<td bgcolor="#FEF2F2" style="padding:10px 14px;border-left:3px solid '
            f'#B91C1C;font:14px {_F};color:#0B1B2B;">'
            "Reviewer's comment: {comment}</td></tr></table>"
            "<p>You can edit and resubmit it.</p>" + _button("Open the request")
        ),
    },
    "FINANCE_READY": {
        "subject": "{number} approved — finance section pending",
        "body_html": (
            "<p>Request <strong>{number}</strong> ({total_cost}) has been fully "
            "approved and needs the finance cost breakdown.</p>" + _FACTS
            + _button("Complete the finance section")
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


def _substitute(text, context, escape=False):
    for key, value in context.items():
        replacement = html.escape(str(value)) if escape else str(value)
        text = text.replace("{" + key + "}", replacement)
    return text


_logo_data_uri_cache = None


def _logo_data_uri():
    # The browser preview can't resolve the Outlook cid: reference, so inline
    # the same PNG the sender attaches.
    global _logo_data_uri_cache
    if _logo_data_uri_cache is None:
        import base64
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "assets", "email_logo.png")
        with open(path, "rb") as f:
            _logo_data_uri_cache = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    return _logo_data_uri_cache


def preview(type_, subject, body_html):
    _require_type(type_)
    ctx = sample_context(type_)
    return {
        "subject": _substitute(subject, ctx),
        "html": email_frame.wrap(_substitute(body_html, ctx, escape=True),
                                 logo_src=_logo_data_uri()),
    }


def render(type_, context, *, redirect_note=None):
    tmpl = get(type_)
    subject = _substitute(tmpl["subject"], context)
    body = _substitute(tmpl["body_html"], context, escape=True)
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
