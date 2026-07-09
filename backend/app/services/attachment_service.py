import uuid

from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Attachment, CapexRequest
from app.services import request_service
from app.services.errors import ServiceError
from app.services.storage import get_storage

_EDITABLE = ("DRAFT", "REJECTED")


def add_attachment(request_id, uploader, filename, content_type, data):
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        raise ServiceError("Request not found.", 404)
    if req.requestor_id != uploader.id:
        raise ServiceError("Only the requestor can attach files.", 403)
    if req.status not in _EDITABLE:
        raise ServiceError("Attachments can only be changed while the request is editable.")
    # Sanitize the client-supplied name before it touches the filesystem
    # (path traversal). Keep the original for display.
    safe_name = secure_filename(filename) or "file"
    rel = f"{request_id}/{uuid.uuid4().hex}_{safe_name}"
    get_storage().put(rel, data)
    att = Attachment(request_id=request_id, filename=filename, storage_path=rel,
                     content_type=content_type, size=len(data), uploaded_by_id=uploader.id)
    db.session.add(att)
    db.session.commit()
    return att


def get_attachment(att_id, viewer):
    att = db.session.get(Attachment, att_id)
    if att is None:
        raise ServiceError("Attachment not found.", 404)
    if not request_service.can_view(att.request, viewer):
        raise ServiceError("You do not have access to this attachment.", 403)
    return att, get_storage().get(att.storage_path)


def delete_attachment(att_id, viewer):
    att = db.session.get(Attachment, att_id)
    if att is None:
        raise ServiceError("Attachment not found.", 404)
    if att.request.requestor_id != viewer.id:
        raise ServiceError("Only the requestor can delete attachments.", 403)
    if att.request.status not in _EDITABLE:
        raise ServiceError("Attachments can only be changed while the request is editable.")
    get_storage().delete(att.storage_path)
    db.session.delete(att)
    db.session.commit()
