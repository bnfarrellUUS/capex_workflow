from app.extensions import db
from app.models import RequestComment
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
