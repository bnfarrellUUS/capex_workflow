import pytest

from app.extensions import db
from app.models import RequestComment
from app.services import comment_service
from app.services.errors import ServiceError
from tests.factories import make_user, make_division, make_draft


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
