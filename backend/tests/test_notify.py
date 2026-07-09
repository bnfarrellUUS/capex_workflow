from app.extensions import db
from app.models import NotificationLog
from app.services import notify
from tests.factories import make_user, make_division, make_draft


def test_send_email_logs_notification(app):
    notify.send_email("a@x.com", "Hi", "Body", None, "ASSIGNED")
    row = db.session.query(NotificationLog).one()
    assert row.recipient == "a@x.com" and row.type == "ASSIGNED"


def test_send_email_delivers_redirected_when_enabled(app, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda to, subject, body: sent.update(to=to, subject=subject, body=body))
    app.config["EMAIL_ENABLED"] = True
    app.config["EMAIL_REDIRECT_TO"] = "me@uus.com"

    notify.send_email("real@x.com", "Subj", "Body text", None, "ASSIGNED")

    assert sent["to"] == "me@uus.com"          # redirected, not the real recipient
    assert "real@x.com" in sent["body"]        # intended recipient noted in body
    assert "Body text" in sent["body"]
    # the log row is still recorded against the intended recipient
    assert db.session.query(NotificationLog).one().recipient == "real@x.com"


def test_send_email_delivery_failure_never_raises(app, monkeypatch):
    def boom(to, subject, body):
        raise RuntimeError("Outlook not running")
    monkeypatch.setattr("app.services.email_outlook.send", boom)
    app.config["EMAIL_ENABLED"] = True

    # Must not propagate — a delivery failure can't block a workflow transition.
    notify.send_email("real@x.com", "Subj", "Body", None, "ASSIGNED")
    assert db.session.query(NotificationLog).count() == 1


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
