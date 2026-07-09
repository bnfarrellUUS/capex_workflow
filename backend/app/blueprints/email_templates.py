from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.email_template import EmailTemplateIn, EmailTemplatePreviewIn
from app.services import email_template_service as ets

bp = Blueprint("email_templates", __name__, url_prefix="/api/email-templates")


@bp.get("")
@require_roles("ADMIN")
def list_templates():
    out = []
    for t in ets.TYPES:
        d = ets.get(t)
        out.append({"type": t, "name": ets.NAMES[t], "subject": d["subject"],
                    "enabled": d["enabled"], "is_custom": d["is_custom"]})
    return jsonify(out)


def _template_out(data):
    # Every endpoint that returns a template must have the same shape: the
    # client caches these responses interchangeably, and a missing field
    # (tokens, previously only added on GET) crashed the editor after Save.
    data["tokens"] = ets.TOKENS[data["type"]]
    return jsonify(data)


@bp.get("/<type_>")
@require_roles("ADMIN")
def get_template(type_):
    return _template_out(ets.get(type_))


@bp.put("/<type_>")
@require_roles("ADMIN")
def save_template(type_):
    payload = EmailTemplateIn(**(request.get_json(silent=True) or {}))
    return _template_out(ets.save(type_, payload.subject, payload.body_html, payload.enabled))


@bp.post("/<type_>/save-as-default")
@require_roles("ADMIN")
def save_as_default(type_):
    return _template_out(ets.save_as_default(type_))


@bp.post("/<type_>/reset")
@require_roles("ADMIN")
def reset_template(type_):
    return _template_out(ets.reset(type_))


@bp.post("/<type_>/preview")
@require_roles("ADMIN")
def preview_template(type_):
    payload = EmailTemplatePreviewIn(**(request.get_json(silent=True) or {}))
    return jsonify(ets.preview(type_, payload.subject, payload.body_html))
