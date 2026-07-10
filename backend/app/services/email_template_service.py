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

# The editable body must be HTML that Quill can round-trip unchanged —
# paragraphs, bold, blockquote. Structured/presentational pieces (the CTA
# button) live in the locked frame instead: Quill strips bgcolor/padding/VML,
# which previously turned the saved button into invisible white-on-white text.
_FACTS = (
    "<p><br></p>"
    "<p>Requested by: <strong>{requestor}</strong></p>"
    "<p>Division: {division}</p>"
    "<p>Total cost: <strong>{total_cost}</strong></p>"
)

# Label of the locked CTA button the frame renders below the body.
BUTTON_LABELS = email_frame.BUTTON_LABELS

DEFAULTS = {
    "ASSIGNED": {
        "subject": "Action needed: {number} awaiting your {level} approval",
        "body_html": (
            "<p>Request <strong>{number}</strong> needs your <strong>{level}</strong> "
            "approval.</p>" + _FACTS
        ),
    },
    "APPROVED": {
        "subject": "{number} was approved",
        "body_html": (
            "<p>Your request <strong>{number}</strong> ({total_cost}) was "
            "<strong>approved</strong>. It is now with Finance for completion.</p>"
        ),
    },
    "REJECTED": {
        "subject": "{number} was rejected",
        "body_html": (
            "<p>Your request <strong>{number}</strong> ({total_cost}) was "
            "<strong>rejected</strong>.</p><p><br></p>"
            "<blockquote>Reviewer's comment: {comment}</blockquote><p><br></p>"
            "<p>You can edit and resubmit it.</p>"
        ),
    },
    "FINANCE_READY": {
        "subject": "{number} approved — finance section pending",
        "body_html": (
            "<p>Request <strong>{number}</strong> ({total_cost}) has been fully "
            "approved and needs the finance cost breakdown.</p>" + _FACTS
        ),
    },
}


def _polish(body_html):
    """Give Quill's bare tags the inline styles email clients need, matching
    what the Quill editor shows: paragraphs are margin-0 (spacing comes from
    blank lines), blockquotes get the editor's gray-bar look."""
    return (body_html
            .replace("<p>", '<p style="margin:0;">')
            .replace("<blockquote>",
                     '<blockquote style="margin:12px 0;padding:4px 0 4px 16px;'
                     'border-left:4px solid #CBD5E1;color:#475569;">'))


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
            "button_label": BUTTON_LABELS[type_],
        }
    return {
        "type": type_, "name": NAMES[type_],
        "subject": row.subject, "body_html": row.body_html, "enabled": row.enabled,
        "default_subject": row.default_subject,
        "default_body_html": row.default_body_html,
        "is_custom": True,
        "button_label": BUTTON_LABELS[type_],
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


_asset_data_uris = {}


def _asset_data_uri(name):
    # The browser preview can't resolve Outlook's cid: references, so inline
    # the same PNGs the sender attaches.
    if name not in _asset_data_uris:
        import base64
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "assets",
                            email_frame.ASSET_FILES[name])
        with open(path, "rb") as f:
            _asset_data_uris[name] = ("data:image/png;base64,"
                                      + base64.b64encode(f.read()).decode())
    return _asset_data_uris[name]


def preview(type_, subject, body_html):
    _require_type(type_)
    ctx = sample_context(type_)
    body = _polish(_substitute(body_html, ctx, escape=True))
    return {
        "subject": _substitute(subject, ctx),
        "html": email_frame.wrap(body, button_type=type_, button_href=ctx["link"],
                                 asset_src=_asset_data_uri),
    }


def render(type_, context, *, redirect_note=None):
    tmpl = get(type_)
    subject = _substitute(tmpl["subject"], context)
    body = _polish(_substitute(tmpl["body_html"], context, escape=True))
    return {
        "subject": subject,
        "html": email_frame.wrap(body, redirect_note=redirect_note,
                                 button_type=type_,
                                 button_href=context.get("link")),
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
