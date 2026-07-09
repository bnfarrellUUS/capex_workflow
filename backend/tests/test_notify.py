from app.extensions import db
from app.models import NotificationLog
from app.services import notify
from tests.factories import make_user, make_division, make_draft


def test_send_email_logs_notification(app):
    notify.send_email("a@x.com", "Hi", "Body", None, "ASSIGNED")
    row = db.session.query(NotificationLog).one()
    assert row.recipient == "a@x.com" and row.type == "ASSIGNED"


def test_notify_assignment_notifies_current_level_approvers(app):
    approver = make_user("appr")
    req_owner = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    req = make_draft(req_owner.id, div.id)
    req.current_level = 1
    req.status = "PENDING_L1"
    db.session.commit()
    notify.notify_assignment(req)
    row = db.session.query(NotificationLog).filter_by(type="ASSIGNED").one()
    assert row.recipient == approver.email
