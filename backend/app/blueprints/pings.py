"""Pings. Thin routes; everything lives in ping_service.

No require_roles: every role pings, and the directory is unscoped by design
(spec section 5). login_required alone is the gate. Static paths (unread_count,
directory, suggestions) are declared before /<ping_id> so Flask never treats
them as ids.
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.schemas.pings import PingCreateIn, PingReplyIn
from app.services import ping_service
from app.services.errors import ServiceError

bp = Blueprint("pings", __name__, url_prefix="/api/pings")


@bp.get("/unread_count")
@login_required
def unread_count():
    return jsonify(count=ping_service.unread_count(current_user))


@bp.get("")
@login_required
def list_pings():
    box = request.args.get("box") or "inbox"
    return jsonify(pings=ping_service.list_pings(current_user, box))


@bp.get("/directory")
@login_required
def directory():
    return jsonify(users=ping_service.directory())


@bp.get("/suggestions")
@login_required
def suggestions():
    request_id = request.args.get("request_id")
    if not request_id:
        raise ServiceError("request_id is required.", 400)
    return jsonify(users=ping_service.suggested_recipients(current_user, request_id))


@bp.get("/<ping_id>")
@login_required
def get_ping(ping_id):
    return jsonify(ping=ping_service.get_ping(current_user, ping_id))


@bp.post("")
@login_required
def create_ping():
    data = PingCreateIn(**(request.get_json(silent=True) or {}))
    ping = ping_service.create_ping(
        current_user, recipient_ids=data.recipient_ids, note=data.note,
        request_id=data.request_id)
    return jsonify(ping=ping_service.get_ping(current_user, ping.id))


@bp.post("/<ping_id>/reply")
@login_required
def reply(ping_id):
    data = PingReplyIn(**(request.get_json(silent=True) or {}))
    ping_service.reply(current_user, ping_id, data.note)
    return jsonify(ping=ping_service.get_ping(current_user, ping_id))


@bp.post("/<ping_id>/done")
@login_required
def done(ping_id):
    return jsonify(ping=ping_service.complete_ping(current_user, ping_id))


@bp.post("/<ping_id>/reopen")
@login_required
def reopen(ping_id):
    return jsonify(ping=ping_service.reopen_ping(current_user, ping_id))
