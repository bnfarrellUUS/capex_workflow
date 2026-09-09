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


def test_detail_stamps_read_for_the_recipient_only(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    b = make_user("ben")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id, b.id], note="Hi")

    assert ping_service.unread_count(a) == 1
    assert ping_service.unread_count(b) == 1

    ping_service.get_ping(a, ping.id)

    # Read is PERSONAL: Ann's open must not clear Ben's badge.
    assert ping_service.unread_count(a) == 0
    assert ping_service.unread_count(b) == 1


def test_detail_refuses_a_third_party(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    nosy = make_user("nosy")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id], note="Hi")

    with pytest.raises(ServiceError) as excinfo:
        ping_service.get_ping(nosy, ping.id)
    assert excinfo.value.status == 403


def test_detail_404s_on_an_unknown_ping_and_on_a_replys_id(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    reply = ping_service.create_ping(sender, recipient_ids=[a.id], note="Reply",
                                     parent_id=root.id)
    for bad in ("no-such-id", reply.id):
        with pytest.raises(ServiceError) as excinfo:
            ping_service.get_ping(a, bad)
        assert excinfo.value.status == 404


def test_a_reply_only_recipient_may_open_the_conversation_their_inbox_lists(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ben = make_user("ben")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    # Ben is addressed only on the REPLY, never on the root -- exactly the case
    # list_pings's roots_via_replies puts in his inbox, so get_ping must agree
    # or the inbox lists what the detail refuses.
    ping_service.create_ping(a, recipient_ids=[ben.id], note="Reply",
                             parent_id=root.id)

    assert [p["id"] for p in ping_service.list_pings(ben, "inbox")] == [root.id]
    assert ping_service.unread_count(ben) == 1
    detail = ping_service.get_ping(ben, root.id)
    assert [r["note"] for r in detail["replies"]] == ["Reply"]
    assert ping_service.unread_count(ben) == 0


def test_detail_has_iso_timestamps(app):
    import re

    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id], note="Hi")
    detail = ping_service.get_ping(a, ping.id)
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", detail["created_at"])
    assert re.match(r"^\d{4}-\d{2}-\d{2}T", detail["recipients"][0]["read_at"])


def test_request_summary_is_visible_to_the_requestor(app):
    from app.services import ping_service
    from tests.factories import make_division, make_draft

    owner = make_user("owner", roles='["REQUESTOR"]')
    div = make_division()
    req = make_draft(owner.id, div.id)
    rae = make_user("rae")

    ping = ping_service.create_ping(rae, recipient_ids=[owner.id], note="Question",
                                    request_id=req.id)

    assert ping_service.get_ping(owner, ping.id)["request"]["visible"] is True
    assert ping_service.get_ping(rae, ping.id)["request"]["visible"] is False


def test_done_is_shared_and_earliest_tick_wins(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    b = make_user("ben")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id, b.id], note="Job")

    ping_service.complete_ping(a, ping.id)
    ping_service.complete_ping(b, ping.id)

    # One job, not one job each: Ann closed it for the roster and keeps the credit.
    for viewer in (a, b, sender):
        assert ping_service.get_ping(viewer, ping.id)["done_by"] == "Ann"
    roster = {r["name"]: r for r in ping_service.get_ping(a, ping.id)["recipients"]}
    # Ben's own tick is still recorded on his row.
    assert roster["Ben"]["completed_at"] is not None


def test_reopen_clears_this_persons_tick_and_falls_back_to_the_next_ticker(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    b = make_user("ben")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id, b.id], note="Job")
    ping_service.complete_ping(a, ping.id)
    ping_service.complete_ping(b, ping.id)
    ping_service.reopen_ping(a, ping.id)
    assert ping_service.get_ping(a, ping.id)["done_by"] == "Ben"
    ping_service.reopen_ping(b, ping.id)
    assert ping_service.get_ping(a, ping.id)["done_by"] is None


def test_done_and_reopen_refuse_a_non_recipient(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id], note="Job")
    # The sender is not on the roster, so the tick is not theirs to make.
    for fn in (ping_service.complete_ping, ping_service.reopen_ping):
        with pytest.raises(ServiceError) as excinfo:
            fn(sender, ping.id)
        assert excinfo.value.status == 403


def test_a_reply_returns_the_conversation_to_the_senders_inbox(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ping = ping_service.create_ping(sender, recipient_ids=[a.id], note="Question")

    assert ping_service.list_pings(sender, "inbox") == []
    ping_service.reply(a, ping.id, "Answer")

    inbox = ping_service.list_pings(sender, "inbox")
    assert [p["id"] for p in inbox] == [ping.id]
    assert inbox[0]["reply_count"] == 1
    assert inbox[0]["unread_for_me"] is True      # the unread REPLY counts
    assert "Answer" in inbox[0]["search_blob"]

    ping_service.get_ping(sender, ping.id)
    assert ping_service.list_pings(sender, "inbox")[0]["unread_for_me"] is False


def test_a_later_reply_reaches_everyone_the_conversation_has_ever_addressed(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ben = make_user("ben")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    # A reply that added Ben -- a recipient the root never named.
    ping_service.create_ping(a, recipient_ids=[sender.id, ben.id],
                             note="Bringing Ben in", parent_id=root.id)

    further = ping_service.reply(sender, root.id, "Following up")
    assert ben.id in {r["user_id"] for r in ping_service._roster(further.id)}


def test_a_deactivated_participant_does_not_block_replies_to_the_rest(app):
    from app.services import ping_service

    sender = make_user("sam")
    a = make_user("ann")
    ben = make_user("ben")
    root = ping_service.create_ping(sender, recipient_ids=[a.id, ben.id], note="Root")
    ben.active = False
    db.session.commit()

    further = ping_service.reply(sender, root.id, "Following up")
    recipients = {r["user_id"] for r in ping_service._roster(further.id)}
    assert a.id in recipients and ben.id not in recipients


def test_reply_refuses_a_non_participant(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    sender = make_user("sam")
    a = make_user("ann")
    nosy = make_user("nosy")
    root = ping_service.create_ping(sender, recipient_ids=[a.id], note="Root")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.reply(nosy, root.id, "Butting in")
    assert excinfo.value.status == 403


def test_directory_is_unscoped_but_excludes_inactive(app):
    from app.services import ping_service
    from tests.factories import make_division

    div = make_division()
    dee = make_user("dee", roles='["ADMIN"]')
    dee.division_id = div.id
    make_user("eli", roles='["REQUESTOR"]')
    gone = make_user("gone")
    gone.active = False
    db.session.commit()

    users = {u["name"]: u for u in ping_service.directory()}
    assert "Dee" in users and "Eli" in users and "Gone" not in users
    assert users["Dee"]["roles"] == ["ADMIN"]
    assert users["Dee"]["division_name"] == "100 — Field Services"
    assert users["Eli"]["division_name"] is None


def test_suggestions_are_the_requestor_and_the_pending_pool_minus_the_viewer(app):
    from app.services import ping_service, workflow_service
    from tests.factories import make_division, make_draft, set_thresholds

    owner = make_user("owner", roles='["REQUESTOR"]')
    l1 = make_user("lone")
    l3 = make_user("lthree")
    div = make_division(l1_approver_id=l1.id)
    set_thresholds(l3_approver=l3.id)
    req = make_draft(owner.id, div.id)            # 30000 < L1 cap, so PENDING_L1
    workflow_service.submit(req.id, owner.id)
    assert req.status == "PENDING_L1"

    viewer = make_user("viewer")
    ids = [u["id"] for u in ping_service.suggested_recipients(viewer, req.id)]
    assert set(ids) == {owner.id, l1.id}

    # The viewer never suggests themself.
    ids = [u["id"] for u in ping_service.suggested_recipients(l1, req.id)]
    assert ids == [owner.id]


def test_suggestions_switch_to_finance_once_approved(app):
    from app.services import ping_service
    from tests.factories import make_division, make_draft

    owner = make_user("owner", roles='["REQUESTOR"]')
    fin = make_user("fin", roles='["FINANCE"]')
    make_user("approver")
    div = make_division()
    req = make_draft(owner.id, div.id)
    req.status = "APPROVED"
    db.session.commit()

    viewer = make_user("viewer")
    ids = {u["id"] for u in ping_service.suggested_recipients(viewer, req.id)}
    assert ids == {owner.id, fin.id}


def test_suggestions_404_an_unknown_request(app):
    from app.services import ping_service
    from app.services.errors import ServiceError

    viewer = make_user("viewer")
    with pytest.raises(ServiceError) as excinfo:
        ping_service.suggested_recipients(viewer, "no-such-request")
    assert excinfo.value.status == 404
