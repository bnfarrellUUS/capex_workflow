"""Comments on a request: a side conversation that changes no workflow state.

Authorization is deliberately delegated to `request_service.get_request`, so
"if you can see the request, you can comment on it" needs no second rule to
keep in sync.
"""
from app.extensions import db
from app.models import RequestComment
from app.services import request_service


def add_comment(request_id, viewer, body):
    req = request_service.get_request(request_id, viewer)
    comment = RequestComment(request_id=req.id, author_id=viewer.id, body=body)
    db.session.add(comment)
    db.session.commit()
    return comment
