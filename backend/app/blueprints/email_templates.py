from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.email_template import EmailTemplateIn, EmailTemplatePreviewIn
from app.services import email_template_service as ets

bp = Blueprint("email_templates", __name__, url_prefix="/api/email-templates")


@bp.get("")
@require_roles("ADMIN")
def list_templates():
    return jsonify([
        {"type": t, "name": ets.NAMES[t], "subject": ets.get(t)["subject"],
         "enabled": ets.get(t)["enabled"], "is_custom": ets.get(t)["is_custom"]}
        for t in ets.TYPES
    ])


@bp.get("/<type_>")
@require_roles("ADMIN")
def get_template(type_):
    data = ets.get(type_)
    data["tokens"] = ets.TOKENS[type_]
    return jsonify(data)


@bp.put("/<type_>")
@require_roles("ADMIN")
def save_template(type_):
    payload = EmailTemplateIn(**(request.get_json(silent=True) or {}))
    return jsonify(ets.save(type_, payload.subject, payload.body_html, payload.enabled))


@bp.post("/<type_>/save-as-default")
@require_roles("ADMIN")
def save_as_default(type_):
    return jsonify(ets.save_as_default(type_))


@bp.post("/<type_>/reset")
@require_roles("ADMIN")
def reset_template(type_):
    return jsonify(ets.reset(type_))


@bp.post("/<type_>/preview")
@require_roles("ADMIN")
def preview_template(type_):
    payload = EmailTemplatePreviewIn(**(request.get_json(silent=True) or {}))
    ets._require_type(type_)
    ctx = ets.sample_context(type_)
    subject = ets._substitute(payload.subject, ctx)
    from app.services import email_frame
    html = email_frame.wrap(ets._substitute(payload.body_html, ctx))
    return jsonify({"subject": subject, "html": html})
