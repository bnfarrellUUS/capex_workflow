"""The SendGrid sender: the payload it posts, and how notify picks it.

SendGrid's v3 API is called directly (no SDK), through email_sendgrid._post,
which every test replaces -- nothing here touches the network.
"""

import base64
import json
import os

import pytest

from app import create_app
from app.config import TestConfig
from app.services import email_frame, email_sendgrid, notify

ASSETS = os.path.join(os.path.dirname(email_sendgrid.__file__), "..", "assets")


@pytest.fixture
def sendgrid_app(app):
    app.config.update(EMAIL_BACKEND="sendgrid", SENDGRID_API_KEY="SG.test-key",
                      EMAIL_FROM="capri@uniteduptime.com", EMAIL_FROM_NAME="CAPRI")
    return app


@pytest.fixture
def posted(monkeypatch):
    calls = []

    def fake_post(url, payload, headers):
        calls.append({"url": url, "payload": json.loads(payload), "headers": headers})
        return 202, b""

    monkeypatch.setattr(email_sendgrid, "_post", fake_post)
    return calls


def test_html_message_payload(sendgrid_app, posted):
    html = '<img src="cid:capri-header"><p>Hi</p><img src="cid:capri-btn-approved">'
    email_sendgrid.send("jane@uniteduptime.com", "Subject", "", html=html)

    call = posted[0]
    assert call["url"] == "https://api.sendgrid.com/v3/mail/send"
    assert call["headers"]["Authorization"] == "Bearer SG.test-key"
    p = call["payload"]
    assert p["personalizations"] == [{"to": [{"email": "jane@uniteduptime.com"}]}]
    assert p["from"] == {"email": "capri@uniteduptime.com", "name": "CAPRI"}
    assert p["subject"] == "Subject"
    assert p["content"] == [{"type": "text/html", "value": html}]
    # The account is shared with other apps, so every send is tagged.
    assert p["categories"] == ["capri"]


def test_only_referenced_brand_images_travel_inline(sendgrid_app, posted):
    html = '<img src="cid:capri-header"><img src="cid:capri-btn-approved">'
    email_sendgrid.send("jane@uniteduptime.com", "S", "", html=html)

    atts = {a["content_id"]: a for a in posted[0]["payload"]["attachments"]}
    assert set(atts) == {"capri-header", "capri-btn-approved"}
    header = atts["capri-header"]
    assert header["disposition"] == "inline"
    assert header["type"] == "image/png"
    with open(os.path.join(ASSETS, email_frame.ASSET_FILES["header"]), "rb") as fh:
        assert base64.b64decode(header["content"]) == fh.read()


def test_file_attachments_are_ordinary_downloads(sendgrid_app, posted):
    email_sendgrid.send("jane@uniteduptime.com", "S", "", html="<p>x</p>",
                        attachments=[("CX000001.pdf", b"%PDF-1.4 test")])

    [att] = posted[0]["payload"]["attachments"]
    assert att == {"content": base64.b64encode(b"%PDF-1.4 test").decode(),
                   "filename": "CX000001.pdf", "type": "application/pdf",
                   "disposition": "attachment"}


def test_plain_text_message(sendgrid_app, posted):
    email_sendgrid.send("jane@uniteduptime.com", "S", "just text")
    p = posted[0]["payload"]
    assert p["content"] == [{"type": "text/plain", "value": "just text"}]
    assert "attachments" not in p


def test_a_rejected_send_raises_without_the_key(sendgrid_app, monkeypatch):
    monkeypatch.setattr(email_sendgrid, "_post",
                        lambda *a: (403, b'{"errors":[{"message":"forbidden"}]}'))
    with pytest.raises(RuntimeError) as exc:
        email_sendgrid.send("jane@uniteduptime.com", "S", "x")
    assert "403" in str(exc.value)
    assert "SG.test-key" not in str(exc.value)


def test_notify_sends_through_sendgrid_when_selected(sendgrid_app, monkeypatch):
    sendgrid_app.config["EMAIL_ENABLED"] = True
    sent = []
    monkeypatch.setattr("app.services.email_sendgrid.send",
                        lambda to, subject, body, html=None, attachments=None: sent.append(to))
    monkeypatch.setattr("app.services.email_outlook.send",
                        lambda *a, **k: pytest.fail("Outlook must not be used"))
    notify.send_email("jane@uniteduptime.com", "Hello", "Body")
    assert sent == ["bryan.farrell@uniteduptime.com"]  # Test mode redirect


def test_health_reports_sendgrid(sendgrid_app, client):
    sendgrid_app.config["EMAIL_ENABLED"] = True
    assert client.get("/api/health").get_json()["email_backend"] == "sendgrid"


class _SendGridOn(TestConfig):
    EMAIL_ENABLED = True
    EMAIL_BACKEND = "sendgrid"
    SENDGRID_API_KEY = "SG.test-key"
    EMAIL_FROM = "capri@uniteduptime.com"


def test_complete_sendgrid_config_starts():
    create_app(_SendGridOn)


@pytest.mark.parametrize("missing", ["SENDGRID_API_KEY", "EMAIL_FROM"])
def test_enabled_sendgrid_without_key_or_sender_refuses_to_start(missing):
    cfg = type("Incomplete", (_SendGridOn,), {missing: None})
    with pytest.raises(RuntimeError, match=missing):
        create_app(cfg)


def test_sendgrid_selected_but_email_off_still_starts():
    """EMAIL_ENABLED=0 sends nothing, so an unfinished SendGrid setup is fine."""
    cfg = type("Off", (_SendGridOn,), {"EMAIL_ENABLED": False, "SENDGRID_API_KEY": None})
    create_app(cfg)


def test_unknown_backend_refuses_to_start():
    cfg = type("Typo", (TestConfig,), {"EMAIL_BACKEND": "sendgird"})
    with pytest.raises(RuntimeError, match="EMAIL_BACKEND"):
        create_app(cfg)


def test_record_email_end_to_end_carries_brand_images_and_pdf(sendgrid_app, posted):
    """A real rendered template through notify: the frame's cid: images all go
    inline and the record PDF goes as a download -- the same message Outlook
    would have sent."""
    from app.extensions import db
    from tests.factories import make_division, make_draft, make_user

    sendgrid_app.config["EMAIL_ENABLED"] = True
    owner = make_user("owner", roles='["REQUESTOR"]')
    req = make_draft(owner.id, make_division().id)
    req.status = "APPROVED"
    req.finance_completed = True
    db.session.commit()

    notify.notify_finance_complete(req)

    payload = posted[0]["payload"]
    html = payload["content"][0]["value"]
    atts = payload["attachments"]
    inline = {a["content_id"] for a in atts if a["disposition"] == "inline"}
    referenced = {cid for cid, _ in email_frame.inline_assets(html)}
    assert inline == referenced
    assert {"capri-header", "capri-bottom", "capri-btn-approved"} <= inline
    downloads = [a for a in atts if a["disposition"] == "attachment"]
    assert [d["type"] for d in downloads] == ["application/pdf"]
    assert base64.b64decode(downloads[0]["content"]).startswith(b"%PDF")
