import pytest
from app.services.errors import ServiceError
from app.services import attachment_service, request_service
from tests.factories import make_user


def _draft(owner):
    return request_service.create_draft(owner)


def test_add_and_get_attachment(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _draft(owner)
    att = attachment_service.add_attachment(req.id, owner, "quote.pdf", "application/pdf", b"hello")
    fetched, data = attachment_service.get_attachment(att.id, owner)
    assert data == b"hello" and fetched.filename == "quote.pdf" and fetched.size == 5


def test_upload_owner_only(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    other = make_user("other", roles='["REQUESTOR"]')
    req = _draft(owner)
    with pytest.raises(ServiceError):
        attachment_service.add_attachment(req.id, other, "x.pdf", "application/pdf", b"x")


def test_download_denied_for_stranger(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    stranger = make_user("stranger", roles='["REQUESTOR"]')
    req = _draft(owner)
    att = attachment_service.add_attachment(req.id, owner, "q.pdf", "application/pdf", b"x")
    with pytest.raises(ServiceError):
        attachment_service.get_attachment(att.id, stranger)


def test_delete_attachment(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _draft(owner)
    att = attachment_service.add_attachment(req.id, owner, "q.pdf", "application/pdf", b"x")
    attachment_service.delete_attachment(att.id, owner)
    with pytest.raises(ServiceError):
        attachment_service.get_attachment(att.id, owner)


def test_upload_sanitizes_traversal_filename(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _draft(owner)
    att = attachment_service.add_attachment(req.id, owner, "../../../evil.txt", "text/plain", b"x")
    assert ".." not in att.storage_path
    assert att.storage_path.startswith(req.id + "/")
    _, data = attachment_service.get_attachment(att.id, owner)
    assert data == b"x"


def test_request_out_lists_attachments(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _draft(owner)
    attachment_service.add_attachment(req.id, owner, "q.pdf", "application/pdf", b"x")
    out = request_service.request_out(request_service.get_request(req.id, owner))
    assert out["attachments"][0]["filename"] == "q.pdf"
