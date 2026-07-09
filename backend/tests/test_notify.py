from decimal import Decimal

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
                        lambda to, subject, body, html=None: sent.update(to=to, body=body))
    app.config["EMAIL_ENABLED"] = True
    app.config["EMAIL_REDIRECT_TO"] = "me@uus.com"

    notify.send_email("real@x.com", "Subj", "Body text", None, "ASSIGNED")

    assert sent["to"] == "me@uus.com"          # redirected, not the real recipient
    assert "real@x.com" in sent["body"]        # intended recipient noted in body
    assert "Body text" in sent["body"]
    # the log row is still recorded against the intended recipient
    assert db.session.query(NotificationLog).one().recipient == "real@x.com"


def test_send_email_delivery_failure_never_raises(app, monkeypatch):
    def boom(to, subject, body, html=None):
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


def test_notify_assignment_uses_template_html(app, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda to, subject, body, html=None: sent.update(subject=subject, html=html))
    app.config["EMAIL_ENABLED"] = True
    app.config["APP_BASE_URL"] = "https://capex.example.com"
    approver = make_user("appr")
    owner = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    req = make_draft(owner.id, div.id)
    req.current_level, req.required_levels, req.status = 1, 2, "PENDING_L1"
    req.total_cost = Decimal("82400")
    db.session.commit()

    notify.notify_assignment(req)

    assert sent["html"] is not None and "United Uptime Services" in sent["html"]
    assert "https://capex.example.com/requests/" in sent["html"]
    assert "Level 1 of 2" in sent["html"]
    assert req.number in sent["subject"]


def test_disabled_template_logs_but_does_not_send(app, monkeypatch):
    from app.services import email_template_service as ets
    calls = []
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda *a, **k: calls.append(a))
    app.config["EMAIL_ENABLED"] = True
    approver = make_user("appr")
    owner = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    req = make_draft(owner.id, div.id)
    req.current_level, req.required_levels, req.status = 1, 1, "PENDING_L1"
    db.session.commit()
    ets.save("ASSIGNED", subject="s", body_html="<p>x</p>", enabled=False)

    notify.notify_assignment(req)

    assert calls == []                                        # not sent
    assert db.session.query(NotificationLog).filter_by(type="ASSIGNED").count() == 1
