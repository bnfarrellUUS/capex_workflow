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


def test_create_ping_addresses_everyone_and_dedupes(app):
    from app.models import PingRecipient
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    b = make_user("ben")

    ping = ping_service.create_ping(
        sender, recipient_ids=[a.id, b.id, a.id], note="Please review.")

    rows = db.session.query(PingRecipient).filter_by(ping_id=ping.id).all()
    assert {r.user_id for r in rows} == {a.id, b.id}
    assert len(rows) == 2


def test_create_ping_refuses_a_blank_note(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=[a.id], note="   ")
    assert excinfo.value.status == 400


def test_create_ping_refuses_an_inactive_recipient(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    gone = make_user("gone")
    gone.active = False
    db.session.commit()
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=[gone.id], note="Hi")
    assert excinfo.value.status == 400


def test_create_ping_refuses_too_many_recipients(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    ids = [make_user(f"m{i}").id for i in range(26)]
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=ids, note="Hi")
    assert excinfo.value.status == 400


def test_create_ping_refuses_an_unknown_request(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=[a.id], note="Hi",
                                 request_id="no-such-request")
    assert excinfo.value.status == 400


def test_a_reply_cannot_attach_to_another_reply(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    reply = ping_service.create_ping(sender, recipient_ids=[a.id], note="Reply",
                                     parent_id=root.id)
    with pytest.raises(ServiceError) as excinfo:
        ping_service.create_ping(sender, recipient_ids=[a.id],
                                 note="Reply to reply", parent_id=reply.id)
    assert excinfo.value.status == 400


def test_inbox_lists_roots_for_the_recipient_and_sent_for_the_sender(app):
    from app.services import ping_service

    sender = make_user("sam")
    rae = make_user("rae")
    ping_service.create_ping(sender, recipient_ids=[rae.id], note="First")

    inbox = ping_service.list_pings(rae, "inbox")
    sent = ping_service.list_pings(sender, "sent")
    assert [p["note"] for p in inbox] == ["First"]
    assert [p["note"] for p in sent] == ["First"]
    assert ping_service.list_pings(sender, "inbox") == []
    assert inbox[0]["recipients"][0]["name"] == "Rae"
    assert inbox[0]["unread_for_me"] is True
    assert inbox[0]["request"] is None


def test_list_rejects_an_unknown_box(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    viewer = make_user("sam")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.list_pings(viewer, "drafts")
    assert excinfo.value.status == 400


def test_ordering_is_deterministic_when_timestamps_tie(app):
    from datetime import datetime, timezone

    from app.models import Ping
    from app.services import ping_service

    sender = make_user("sam")
    rae = make_user("rae")
    first = ping_service.create_ping(sender, recipient_ids=[rae.id], note="First")
    second = ping_service.create_ping(sender, recipient_ids=[rae.id], note="Second")

    # Force a genuine tie so the only thing deciding the order is the id
    # tiebreak -- ids are uuid4().hex, NOT monotonic, hence "deterministic",
    # not "insertion order".
    tied_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    db.session.query(Ping).filter(Ping.id.in_([first.id, second.id])).update(
        {"created_at": tied_at}, synchronize_session=False)
    db.session.commit()

    inbox = ping_service.list_pings(rae, "inbox")
    assert [p["id"] for p in inbox] == sorted([first.id, second.id], reverse=True)


def test_summary_carries_the_live_request(app):
    from app.services import ping_service
    from tests.factories import make_division, make_draft

    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    rae = make_user("rae")

    ping_service.create_ping(owner, recipient_ids=[rae.id], note="See this",
                             request_id=req.id)

    summary = ping_service.list_pings(rae, "inbox")[0]["request"]
    assert summary["id"] == req.id
    assert summary["number"] == "CX000001"
    assert summary["status"] == "DRAFT"
    assert summary["requestor_name"] == "Owner"
    assert summary["total_cost"] is not None   # money_str of the stored total
    # Rae is neither the owner nor an approver: she can see the summary, not the request.
    assert summary["visible"] is False
