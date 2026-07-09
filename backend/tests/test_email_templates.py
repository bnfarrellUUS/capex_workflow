from app.extensions import db
from app.models import EmailTemplate


def test_email_template_round_trips(app):
    db.session.add(EmailTemplate(
        type="ASSIGNED", subject="s", body_html="<p>b</p>", enabled=True,
        default_subject="s", default_body_html="<p>b</p>"))
    db.session.commit()
    row = db.session.get(EmailTemplate, "ASSIGNED")
    assert row.enabled is True and row.body_html == "<p>b</p>"
