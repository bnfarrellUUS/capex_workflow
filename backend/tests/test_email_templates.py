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


from app.services import email_template_service as ets
from app.services.errors import ServiceError
import pytest


def test_get_returns_shipped_default_when_no_row(app):
    t = ets.get("ASSIGNED")
    assert t["is_custom"] is False
    assert "{number}" in t["body_html"]
    assert t["enabled"] is True


def test_render_substitutes_tokens_and_frames(app):
    out = ets.render("ASSIGNED", {"number": "CX000042", "level": "Level 2 of 3",
                                  "requestor": "Dana", "division": "12 — FS",
                                  "total_cost": "$1.00", "link": "http://x/req/1"})
    assert "CX000042" in out["html"]
    assert "United Uptime Services" in out["html"]      # framed
    assert "{number}" not in out["html"]


def test_render_leaves_unknown_token_intact(app):
    out = ets.render("APPROVED", {"number": "CX1"})
    # {link} etc. not supplied -> remain literally, not blanked
    assert "{link}" in out["html"] or "{total_cost}" in out["html"]


def test_save_then_reset_reverts_to_shipped_default(app):
    ets.save("APPROVED", subject="Custom", body_html="<p>custom</p>", enabled=True)
    assert ets.get("APPROVED")["is_custom"] is True
    ets.reset("APPROVED")
    t = ets.get("APPROVED")
    assert t["subject"] == ets.DEFAULTS["APPROVED"]["subject"]


def test_save_as_default_then_reset_reverts_to_admin_default(app):
    ets.save("REJECTED", subject="v1", body_html="<p>v1</p>", enabled=True)
    ets.save_as_default("REJECTED")
    ets.save("REJECTED", subject="v2", body_html="<p>v2</p>", enabled=True)
    ets.reset("REJECTED")
    assert ets.get("REJECTED")["subject"] == "v1"


def test_get_unknown_type_raises(app):
    with pytest.raises(ServiceError):
        ets.get("NOPE")


def test_preview_substitutes_sample_data_and_frames(app):
    out = ets.preview("ASSIGNED", "Re: {number}", "<p>{number} — {level}</p>")
    assert out["subject"] == "Re: CX000042"
    assert "CX000042" in out["html"] and "Level 2 of 3" in out["html"]
    assert "United Uptime Services" in out["html"]      # framed


def test_render_escapes_token_values_in_body(app):
    out = ets.render("REJECTED", {"number": "CX1", "total_cost": "$1.00",
                                  "comment": "a < b & <b>bold</b>",
                                  "requestor": "x", "division": "d",
                                  "link": "http://x/r/1"})
    # user-supplied value is escaped, not rendered as real markup
    assert "a &lt; b &amp; &lt;b&gt;bold&lt;/b&gt;" in out["html"]
    assert "<b>bold</b>" not in out["html"]
    # template's own markup and the framed shell remain intact
    assert "United Uptime Services" in out["html"]
