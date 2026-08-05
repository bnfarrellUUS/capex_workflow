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
