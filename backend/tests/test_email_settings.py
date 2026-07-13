import pytest
from pydantic import ValidationError

from app.extensions import db
from app.models import AppSetting, NotificationLog
from app.services import notify, settings_service
from app.schemas.email_settings import EmailSettingsIn
from tests.factories import make_user, make_division, make_draft


# ---- settings_service ----

def test_defaults_to_test_mode_and_config_recipient(app):
    app.config["EMAIL_REDIRECT_TO"] = "tester@uus.com"
    s = settings_service.get_email_settings()
    assert s["mode"] == "test"
    assert s["test_recipient"] == "tester@uus.com"


def test_set_email_settings_persists_to_appsetting(app):
    settings_service.set_email_settings("live", "someone@uus.com")
    assert settings_service.get_email_settings() == {"mode": "live", "test_recipient": "someone@uus.com"}
    # stored in the AppSetting key/value table
    assert db.session.get(AppSetting, "email_mode").value == "live"
    assert db.session.get(AppSetting, "email_test_recipient").value == "someone@uus.com"


# ---- notify honours the mode ----

def _sent_spy(monkeypatch):
    sent = {}
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda to, subject, body, html=None: sent.update(to=to, body=body, html=html))
    return sent


def test_test_mode_redirects_to_test_recipient(app, monkeypatch):
    sent = _sent_spy(monkeypatch)
    app.config["EMAIL_ENABLED"] = True
    settings_service.set_email_settings("test", "tester@uus.com")

    notify.send_email("real@x.com", "Subj", "Body text", None, "ASSIGNED")

    assert sent["to"] == "tester@uus.com"        # redirected to the test recipient
    assert "real@x.com" in sent["body"]          # intended recipient noted
    assert db.session.query(NotificationLog).one().recipient == "real@x.com"


def test_live_mode_sends_to_the_real_recipient_without_banner(app, monkeypatch):
    sent = _sent_spy(monkeypatch)
    app.config["EMAIL_ENABLED"] = True
    settings_service.set_email_settings("live", "tester@uus.com")

    notify.send_email("real@x.com", "Subj", "Body text", None, "ASSIGNED")

    assert sent["to"] == "real@x.com"            # goes to the actual recipient
    assert "Intended recipient" not in sent["body"]


def test_live_mode_template_send_has_no_redirect_banner(app, monkeypatch):
    sent = _sent_spy(monkeypatch)
    app.config["EMAIL_ENABLED"] = True
    settings_service.set_email_settings("live", "tester@uus.com")
    approver = make_user("appr")
    owner = make_user("req", roles='["REQUESTOR"]')
    div = make_division(l1_approver_id=approver.id)
    req = make_draft(owner.id, div.id)
    req.current_level, req.required_levels, req.status = 1, 1, "PENDING_L1"
    db.session.commit()

    notify.notify_assignment(req)

    assert sent["to"] == approver.email
    assert "redirected while testing" not in (sent["html"] or "")


# ---- schema validation ----

def test_schema_rejects_bad_mode():
    with pytest.raises(ValidationError):
        EmailSettingsIn(mode="prod", test_recipient="a@b.com")


def test_schema_rejects_bad_email():
    with pytest.raises(ValidationError):
        EmailSettingsIn(mode="test", test_recipient="not-an-email")


def test_schema_accepts_valid():
    s = EmailSettingsIn(mode="live", test_recipient="a@b.com")
    assert s.mode == "live" and s.test_recipient == "a@b.com"


# ---- API (ADMIN only) ----

def _login_admin(client):
    make_user("admin", roles='["ADMIN"]')
    client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})


def test_settings_endpoint_round_trips(client, app):
    app.config["EMAIL_REDIRECT_TO"] = "tester@uus.com"
    _login_admin(client)
    got = client.get("/api/email-templates/settings").get_json()
    assert got == {"mode": "test", "test_recipient": "tester@uus.com"}

    r = client.put("/api/email-templates/settings",
                   json={"mode": "live", "test_recipient": "ops@uus.com"})
    assert r.status_code == 200
    assert client.get("/api/email-templates/settings").get_json() == {
        "mode": "live", "test_recipient": "ops@uus.com"}


def test_settings_endpoint_requires_admin(client):
    make_user("plain", roles='["REQUESTOR"]')
    client.post("/api/auth/login", json={"username": "plain", "password": "secret123"})
    assert client.get("/api/email-templates/settings").status_code == 403
