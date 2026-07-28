from decimal import Decimal

from app.extensions import db
from app.models import NotificationLog
from app.services import email_template_service as ets
from app.services import notify, settings_service
from tests.factories import make_user, make_division, make_draft, set_thresholds


def _sent_spy(monkeypatch):
    """Capture what reaches the Outlook sender, attachments included."""
    sent = {}

    def fake_send(to, subject, body, html=None, attachments=None):
        sent.update(to=to, subject=subject, html=html, attachments=attachments)

    monkeypatch.setattr("app.services.email_outlook.send", fake_send)
    return sent


def _approved_request(finance_completed=False):
    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    req.status = "APPROVED"
    req.finance_completed = finance_completed
    db.session.commit()
    return req


# ---- the fifth template ----

def test_finance_complete_is_a_real_template_type():
    assert "FINANCE_COMPLETE" in ets.TYPES
    assert ets.NAMES["FINANCE_COMPLETE"]
    assert ets.DEFAULTS["FINANCE_COMPLETE"]["subject"]
    assert ets.TOKENS["FINANCE_COMPLETE"]


def test_finance_complete_renders_its_tokens(app):
    req = _approved_request()
    ctx = ets.context_for(req)
    out = ets.render("FINANCE_COMPLETE", ctx)
    assert req.number in out["subject"]
    assert req.number in out["html"]
    assert "{number}" not in out["html"]


def test_finance_complete_template_is_listed_by_the_api(client):
    make_user("admin", roles='["ADMIN"]')
    client.post("/api/auth/login", json={"email": "admin@x.com", "password": "secret123"})
    types = [t["type"] for t in client.get("/api/email-templates").get_json()]
    assert "FINANCE_COMPLETE" in types


# ---- notify attaches the PDF ----

def test_notify_finance_complete_attaches_the_pdf_to_the_requestor(app, monkeypatch):
    sent = _sent_spy(monkeypatch)
    app.config["EMAIL_ENABLED"] = True
    settings_service.set_email_settings("live", "tester@uus.com")
    req = _approved_request(finance_completed=True)

    notify.notify_finance_complete(req)

    assert sent["to"] == req.requestor.email
    assert len(sent["attachments"]) == 1
    filename, data = sent["attachments"][0]
    assert filename == f"{req.number}.pdf"
    assert data[:5] == b"%PDF-"


def test_notify_finance_complete_logs_the_notification(app):
    req = _approved_request(finance_completed=True)
    notify.notify_finance_complete(req)
    row = db.session.query(NotificationLog).filter_by(type="FINANCE_COMPLETE").one()
    assert row.recipient == req.requestor.email


def test_test_mode_still_redirects_but_keeps_the_attachment(app, monkeypatch):
    sent = _sent_spy(monkeypatch)
    app.config["EMAIL_ENABLED"] = True
    settings_service.set_email_settings("test", "tester@uus.com")
    req = _approved_request(finance_completed=True)

    notify.notify_finance_complete(req)

    assert sent["to"] == "tester@uus.com"
    assert len(sent["attachments"]) == 1


# ---- trigger: first completion only ----

def _finance_login(client):
    make_user("fin", roles='["FINANCE"]')
    client.post("/api/auth/login", json={"email": "fin@x.com", "password": "secret123"})


def _costs():
    return {"cost_machinery": "30000.00"}


def test_first_finance_save_emails_the_requestor(client, app):
    req = _approved_request()
    _finance_login(client)

    r = client.post(f"/api/requests/{req.id}/finance", json=_costs())

    assert r.status_code == 200
    assert db.session.query(NotificationLog).filter_by(type="FINANCE_COMPLETE").count() == 1


def test_a_second_finance_save_emails_nobody(client, app):
    req = _approved_request()
    _finance_login(client)

    client.post(f"/api/requests/{req.id}/finance", json=_costs())
    client.post(f"/api/requests/{req.id}/finance", json={"cost_machinery": "31000.00"})

    assert db.session.query(NotificationLog).filter_by(type="FINANCE_COMPLETE").count() == 1


# ---- manual resend ----

def test_finance_can_resend_the_record(client, app):
    req = _approved_request(finance_completed=True)
    _finance_login(client)

    r = client.post(f"/api/requests/{req.id}/resend-record")

    assert r.status_code == 200
    assert db.session.query(NotificationLog).filter_by(type="FINANCE_COMPLETE").count() == 1


def test_resend_is_refused_before_finance_completes(client, app):
    req = _approved_request(finance_completed=False)
    _finance_login(client)

    r = client.post(f"/api/requests/{req.id}/resend-record")

    assert r.status_code == 400
    assert db.session.query(NotificationLog).filter_by(type="FINANCE_COMPLETE").count() == 0


def test_a_requestor_cannot_resend_the_record(client, app):
    req = _approved_request(finance_completed=True)
    client.post("/api/auth/login", json={"email": "owner@x.com", "password": "secret123"})

    assert client.post(f"/api/requests/{req.id}/resend-record").status_code == 403


def test_admin_can_resend_the_record(client, app):
    req = _approved_request(finance_completed=True)
    make_user("admin", roles='["ADMIN"]')
    client.post("/api/auth/login", json={"email": "admin@x.com", "password": "secret123"})

    assert client.post(f"/api/requests/{req.id}/resend-record").status_code == 200
