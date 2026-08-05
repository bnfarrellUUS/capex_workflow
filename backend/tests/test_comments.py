import pytest

from app.extensions import db
from app.models import NotificationLog, RequestComment
from app.services import comment_service, notify
from app.services.errors import ServiceError
from tests.factories import make_user, make_division, make_draft, set_thresholds


def test_comment_belongs_to_a_request_and_an_author(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)

    db.session.add(RequestComment(request_id=req.id, author_id=owner.id, body="Why this model?"))
    db.session.commit()

    assert [c.body for c in req.comments] == ["Why this model?"]
    assert req.comments[0].author.name == owner.name
    assert req.comments[0].created_at is not None


def test_deleting_a_request_takes_its_comments_with_it(app):
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    db.session.add(RequestComment(request_id=req.id, author_id=owner.id, body="x"))
    db.session.commit()

    db.session.delete(req)
    db.session.commit()

    assert db.session.query(RequestComment).count() == 0


def _owner_and_request():
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    return owner, make_draft(owner.id, div.id)


def test_add_comment_saves_and_returns_it(app):
    owner, req = _owner_and_request()

    c = comment_service.add_comment(req.id, owner, "Is this a replacement?")

    assert c.body == "Is this a replacement?"
    assert c.author_id == owner.id
    assert db.session.query(RequestComment).count() == 1


def test_add_comment_leaves_the_workflow_untouched(app):
    owner, req = _owner_and_request()
    req.status, req.current_level, req.required_levels = "PENDING_L2", 2, 3
    db.session.commit()

    comment_service.add_comment(req.id, owner, "Any update?")

    assert (req.status, req.current_level, req.assignee_id) == ("PENDING_L2", 2, None)


def test_add_comment_rejects_a_viewer_without_access(app):
    owner, req = _owner_and_request()
    stranger = make_user("stranger", roles='["REQUESTOR"]')

    with pytest.raises(ServiceError) as exc:
        comment_service.add_comment(req.id, stranger, "Nosy question")
    assert exc.value.status == 403


def test_add_comment_on_a_missing_request_is_404(app):
    owner, _ = _owner_and_request()

    with pytest.raises(ServiceError) as exc:
        comment_service.add_comment("no-such-id", owner, "Hello?")
    assert exc.value.status == 404


def _login(client, user):
    client.post("/api/auth/login", json={"email": user.email, "password": "secret123"})


def test_post_comment_returns_the_request_with_the_comment(client, app):
    owner, req = _owner_and_request()
    _login(client, owner)

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "Which vendor?"})

    assert r.status_code == 200
    body = r.get_json()
    assert body["id"] == req.id
    assert [c["body"] for c in body["comments"]] == ["Which vendor?"]
    assert body["comments"][0]["author_name"] == owner.name
    assert body["comments"][0]["created_at"] is not None


def test_comments_come_back_oldest_first(client, app):
    owner, req = _owner_and_request()
    _login(client, owner)

    client.post(f"/api/requests/{req.id}/comments", json={"body": "first"})
    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "second"})

    assert [c["body"] for c in r.get_json()["comments"]] == ["first", "second"]


def test_post_comment_rejects_an_empty_body_with_400(client, app):
    owner, req = _owner_and_request()
    _login(client, owner)

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "   "})

    assert r.status_code == 400   # not 500 — see the ValidationError handler bug


def test_post_comment_rejects_an_overlong_body_with_400(client, app):
    owner, req = _owner_and_request()
    _login(client, owner)

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "x" * 4001})

    assert r.status_code == 400


def test_post_comment_from_a_stranger_is_403(client, app):
    owner, req = _owner_and_request()
    stranger = make_user("stranger", roles='["REQUESTOR"]')
    _login(client, stranger)

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "Nosy"})

    assert r.status_code == 403


def test_pool_approver_can_comment(client, app):
    from tests.factories import set_thresholds
    first = make_user("first")
    second = make_user("second")
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division(l1_approver_ids=[first.id, second.id])
    set_thresholds()
    req = make_draft(owner.id, div.id)
    req.status, req.current_level, req.assignee_id = "PENDING_L1", 1, first.id
    db.session.commit()
    _login(client, second)   # in the pool, not the displayed assignee

    r = client.post(f"/api/requests/{req.id}/comments", json={"body": "Is the bid attached?"})

    assert r.status_code == 200
    assert r.get_json()["comments"][0]["author_name"] == second.name


def _pending_l1():
    approver = make_user("appr")
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    set_thresholds()
    req = make_draft(owner.id, div.id)
    req.status, req.current_level, req.required_levels = "PENDING_L1", 1, 1
    db.session.commit()
    return approver, owner, req


def _recipients():
    return {r.recipient for r in db.session.query(NotificationLog)
            .filter_by(type="COMMENT").all()}


def test_requestor_comment_emails_the_current_approvers(app):
    approver, owner, req = _pending_l1()
    c = comment_service.add_comment(req.id, owner, "Any update?")

    notify.notify_comment(req, c)

    assert _recipients() == {approver.email}


def test_approver_comment_emails_the_requestor(app):
    approver, owner, req = _pending_l1()
    c = comment_service.add_comment(req.id, approver, "Is this a replacement?")

    notify.notify_comment(req, c)

    assert _recipients() == {owner.email}


def test_requestor_comment_on_an_approved_request_emails_finance(app):
    approver, owner, req = _pending_l1()
    finance = make_user("fin", roles='["FINANCE"]')
    req.status, req.assignee_id = "APPROVED", None
    db.session.commit()
    c = comment_service.add_comment(req.id, owner, "When is this booked?")

    notify.notify_comment(req, c)

    assert _recipients() == {finance.email}


def test_requestor_comment_on_a_draft_emails_nobody(app):
    owner, req = _owner_and_request()
    c = comment_service.add_comment(req.id, owner, "Note to self")

    notify.notify_comment(req, c)

    assert _recipients() == set()
    assert db.session.query(RequestComment).count() == 1   # the comment still saved


def test_comment_email_renders_the_author_and_body(app, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda to, subject, body, html=None, attachments=None:
                        sent.update(subject=subject, html=html))
    app.config["EMAIL_ENABLED"] = True
    approver, owner, req = _pending_l1()
    c = comment_service.add_comment(req.id, approver, "Where are the bids?")

    notify.notify_comment(req, c)

    assert req.number in sent["subject"]
    assert approver.name in sent["html"]
    assert "Where are the bids?" in sent["html"]


def test_posting_a_comment_through_the_api_sends_the_email(client, app):
    approver, owner, req = _pending_l1()
    _login(client, owner)

    client.post(f"/api/requests/{req.id}/comments", json={"body": "Any update?"})

    assert _recipients() == {approver.email}
