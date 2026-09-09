import pytest

from app.extensions import db
from tests.factories import make_user


def test_ping_tables_exist_and_relate(app):
    from app.models import Ping, PingRecipient

    sender = make_user("sam")
    recipient = make_user("rae")

    ping = Ping(sender_id=sender.id, note="Check the GL account.")
    db.session.add(ping)
    db.session.flush()
    db.session.add(PingRecipient(ping_id=ping.id, user_id=recipient.id))
    db.session.commit()

    assert len(ping.id) == 32          # uuid4().hex, in a String(36) column
    assert ping.parent_id is None
    assert ping.request_id is None
    assert ping.created_at is not None
    row = db.session.query(PingRecipient).one()
    assert row.read_at is None and row.completed_at is None


def test_ping_recipient_is_unique_per_person(app):
    from sqlalchemy.exc import IntegrityError

    from app.models import Ping, PingRecipient

    sender = make_user("sam")
    recipient = make_user("rae")
    ping = Ping(sender_id=sender.id, note="Hello")
    db.session.add(ping)
    db.session.flush()
    db.session.add(PingRecipient(ping_id=ping.id, user_id=recipient.id))
    db.session.add(PingRecipient(ping_id=ping.id, user_id=recipient.id))
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
