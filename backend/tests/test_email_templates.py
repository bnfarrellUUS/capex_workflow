from app.extensions import db
from app.models import EmailTemplate
from app.services import email_frame


def test_email_template_round_trips(app):
    db.session.add(EmailTemplate(
        type="ASSIGNED", subject="s", body_html="<p>b</p>", enabled=True,
        default_subject="s", default_body_html="<p>b</p>"))
    db.session.commit()
    row = db.session.get(EmailTemplate, "ASSIGNED")
    assert row.enabled is True and row.body_html == "<p>b</p>"


def test_frame_wraps_body_and_shows_brand():
    html = email_frame.wrap("<p>Hello</p>")
    assert "<p>Hello</p>" in html
    assert "United Uptime Services" in html
    assert "#0B2A4A" in html          # navy header
    assert "Intended recipient" not in html


def test_frame_redirect_note_banner():
    html = email_frame.wrap("<p>Hi</p>", redirect_note="Intended recipient: a@x.com")
    assert "Intended recipient: a@x.com" in html
