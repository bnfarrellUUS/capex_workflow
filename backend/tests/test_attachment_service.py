import pytest
from app.services.errors import ServiceError
from app.services import attachment_service, request_service
from app.services.workflow_service import submit, approve
from tests.factories import make_user, make_division, set_thresholds, make_draft


def _draft(owner):
    return request_service.create_draft(owner)


def _approved():
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id, costs=("30000",))
    submit(req.id, requestor.id)
    approve(req.id, l1.id)  # required_levels==1 -> APPROVED
    return requestor, req


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


def test_finance_can_attach_and_delete_on_approved(app):
    requestor, req = _approved()
    fin = make_user("fin", roles='["FINANCE"]')
    att = attachment_service.add_attachment(req.id, fin, "invoice.pdf", "application/pdf", b"x")
    assert att.filename == "invoice.pdf"
    attachment_service.delete_attachment(att.id, fin)
    with pytest.raises(ServiceError):
        attachment_service.get_attachment(att.id, fin)


def test_finance_cannot_attach_while_pending(app):
    l1 = make_user("l1")
    requestor = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=l1.id)
    set_thresholds()
    req = make_draft(requestor.id, div.id)
    submit(req.id, requestor.id)  # PENDING_L1
    fin = make_user("fin", roles='["FINANCE"]')
    with pytest.raises(ServiceError):
        attachment_service.add_attachment(req.id, fin, "x.pdf", "application/pdf", b"x")


def test_owner_cannot_attach_once_approved(app):
    requestor, req = _approved()
    with pytest.raises(ServiceError):
        attachment_service.add_attachment(req.id, requestor, "x.pdf", "application/pdf", b"x")


def test_request_out_lists_attachments(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = _draft(owner)
    attachment_service.add_attachment(req.id, owner, "q.pdf", "application/pdf", b"x")
    out = request_service.request_out(request_service.get_request(req.id, owner))
    assert out["attachments"][0]["filename"] == "q.pdf"
