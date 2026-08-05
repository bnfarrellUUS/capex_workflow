from datetime import date
from flask import Blueprint, jsonify, request, Response
from flask_login import login_required, current_user

from app.authz import require_roles
from app.schemas.request import RequestDraft, FinanceIn, CommentIn
from app.services.errors import ServiceError
from app.services import (
    request_service, workflow_service, notify, attachment_service, export_service,
    pdf_service, settings_service, comment_service,
)

bp = Blueprint("requests", __name__, url_prefix="/api/requests")


@bp.get("")
@login_required
def list_requests_route():
    rows = request_service.list_requests(
        current_user,
        scope=request.args.get("scope", "mine"),
        status=request.args.get("status") or None,
        division_id=request.args.get("division_id") or None,
    )
    return jsonify([request_service.request_summary(r) for r in rows])


@bp.get("/export.xlsx")
@login_required
def export_requests_route():
    data = export_service.export_xlsx(
        current_user,
        scope=request.args.get("scope", "mine"),
        status=request.args.get("status") or None,
        division_id=request.args.get("division_id") or None,
        q=request.args.get("q") or None,
    )
    filename = f"capex-requests-{date.today().isoformat()}.xlsx"
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.post("")
@login_required
def create_request():
    req = request_service.create_draft(current_user)
    return jsonify(request_service.request_out(req)), 201


@bp.get("/<request_id>")
@login_required
def get_request(request_id):
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))


@bp.delete("/<request_id>")
@login_required
def delete_request(request_id):
    request_service.delete_draft(request_id, current_user)
    return "", 204


@bp.patch("/<request_id>")
@login_required
def update_request(request_id):
    data = RequestDraft(**(request.get_json(silent=True) or {}))
    req = request_service.update_draft(request_id, current_user, data.model_dump(exclude_unset=True))
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/submit")
@login_required
def submit_request(request_id):
    req = workflow_service.submit(request_id, current_user.id)
    notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/approve")
@login_required
def approve_request(request_id):
    comment = (request.get_json(silent=True) or {}).get("comment")
    req = workflow_service.approve(request_id, current_user.id, comment)
    if req.status == "APPROVED":
        notify.notify_decision(req, True)
        notify.notify_finance_ready(req)
    else:
        notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/reject")
@login_required
def reject_request(request_id):
    comment = (request.get_json(silent=True) or {}).get("comment", "")
    req = workflow_service.reject(request_id, current_user.id, comment)
    notify.notify_decision(req, False, comment)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/resubmit")
@login_required
def resubmit_request(request_id):
    req = workflow_service.resubmit(request_id, current_user.id)
    notify.notify_assignment(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/comments")
@login_required
def add_comment_route(request_id):
    data = CommentIn(**(request.get_json(silent=True) or {}))
    comment_service.add_comment(request_id, current_user, data.body)
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/finance")
@login_required
def finance_request(request_id):
    costs = FinanceIn(**(request.get_json(silent=True) or {})).model_dump()
    req = workflow_service.complete_finance(request_id, current_user.id, costs)
    # Send the requestor their record copy on the FIRST completion only; the
    # audit trail already logs every FINANCE_COMPLETED, so exactly one means
    # this save was the first. Later re-saves stay silent (use resend-record).
    if sum(1 for a in req.actions if a.action == "FINANCE_COMPLETED") == 1:
        notify.notify_finance_complete(req)
    return jsonify(request_service.request_out(req))


@bp.post("/<request_id>/resend-record")
@require_roles("FINANCE", "ADMIN")
def resend_record(request_id):
    req = request_service.get_request(request_id, current_user)
    if not req.finance_completed:
        raise ServiceError("The finance section is not complete yet.")
    notify.notify_finance_complete(req)
    return jsonify(request_service.request_out(req))


@bp.get("/<request_id>/pdf")
@login_required
def request_pdf(request_id):
    # get_request applies the detail page's visibility rule (404/403).
    req = request_service.get_request(request_id, current_user)
    data = pdf_service.build_request_pdf(req, settings_service.get_hidden_sections())
    return Response(data, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{pdf_service.pdf_filename(req)}"',
    })


@bp.post("/<request_id>/attachments")
@login_required
def upload_attachment(request_id):
    f = request.files.get("file")
    if f is None:
        return jsonify(error="No file provided."), 400
    attachment_service.add_attachment(request_id, current_user, f.filename,
                                      f.mimetype or "application/octet-stream", f.read())
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))


@bp.get("/<request_id>/attachments/<att_id>")
@login_required
def download_attachment(request_id, att_id):
    att, data = attachment_service.get_attachment(att_id, current_user)
    return Response(data, mimetype=att.content_type,
                    headers={"Content-Disposition": f'attachment; filename="{att.filename}"'})


@bp.delete("/<request_id>/attachments/<att_id>")
@login_required
def delete_attachment_route(request_id, att_id):
    attachment_service.delete_attachment(att_id, current_user)
    req = request_service.get_request(request_id, current_user)
    return jsonify(request_service.request_out(req))
