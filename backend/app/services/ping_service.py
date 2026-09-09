"""Pings: in-app work routing with a conversation attached.

Two rules here are not obvious and are the whole point of the feature:

* **Read is personal.** Each recipient's own PingRecipient row carries read_at,
  so a group ping read by two of five is still unread for the other three.
* **Done is SHARED.** A group ping is one job, not one job each: whoever ticks
  it first closes it for the roster, and done_by names them. Derived here at
  read time rather than stored, so no schema or backfill is involved and each
  person's own tick survives if the rule is ever revisited.

Pings are deliberately UNSCOPED (spec section 5): anyone signed in can ping
anyone signed in, because the value is reaching whoever can answer fastest.
Do not add a scope filter to the directory.

Ported from SCORE's ping_service (bid_template/bid_app) with the bid, customer,
approval-rule and line context replaced by one optional request_id.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.extensions import db
from app.models import CapexRequest, Ping, PingRecipient, User
from app.serialization import money_str
from app.services import request_service
from app.services.errors import ServiceError

MAX_RECIPIENTS = 25


def _active_users(ids: list[str]) -> list[User]:
    rows = db.session.scalars(select(User).where(User.id.in_(ids))).all()
    found = {u.id: u for u in rows if u.active}
    missing = [i for i in ids if i not in found]
    if missing:
        raise ServiceError("Every recipient must be an active user.", 400)
    return [found[i] for i in ids]


def create_ping(sender, *, recipient_ids: list[str], note: str,
                request_id: str | None = None,
                parent_id: str | None = None) -> Ping:
    note = (note or "").strip()
    if not note:
        raise ServiceError("A ping needs a note.", 400)

    # dict.fromkeys dedupes while preserving the order the sender picked.
    ids = list(dict.fromkeys(recipient_ids or []))
    if not ids:
        raise ServiceError("A ping needs at least one recipient.", 400)
    if len(ids) > MAX_RECIPIENTS:
        raise ServiceError(
            f"A ping can go to at most {MAX_RECIPIENTS} people.", 400)
    _active_users(ids)

    if parent_id is not None:
        parent = db.session.get(Ping, parent_id)
        if parent is None or parent.parent_id is not None:
            # Replies attach to the ROOT, never to another reply: a thread is
            # exactly two levels deep.
            raise ServiceError("A reply must attach to a conversation.", 400)

    if request_id is not None and db.session.get(CapexRequest, request_id) is None:
        raise ServiceError("Unknown request.", 400)

    ping = Ping(parent_id=parent_id, sender_id=sender.id, note=note,
                request_id=request_id)
    db.session.add(ping)
    db.session.flush()
    for uid in ids:
        db.session.add(PingRecipient(ping_id=ping.id, user_id=uid))
    db.session.commit()
    return ping


def _iso(dt) -> str | None:
    """Datetimes leave the API isoformatted, like request_service does -- a raw
    datetime handed to jsonify serializes as an HTTP-date."""
    return dt.isoformat() if dt else None


def apply_shared_done(payload: dict, recipients: list[dict]) -> dict:
    """Overlay the SHARED completion onto a conversation.

    Earliest tick wins, so a second person ticking through a stale page cannot
    rewrite who finished it -- their tick is still on their own roster row.
    `recipients` carries raw datetimes (see `_roster`); sort on those, then
    isoformat only the value that leaves in the payload.
    """
    done = sorted((r["completed_at"], r["name"]) for r in recipients
                  if r.get("completed_at"))
    payload["completed_at"] = _iso(done[0][0]) if done else None
    payload["done_by"] = done[0][1] if done else None
    return payload


def _roster(ping_id: str) -> list[dict]:
    """Raw datetimes -- `apply_shared_done` sorts on them. `_serialize_recipient`
    isoformats them for the API payload."""
    rows = db.session.execute(
        select(PingRecipient, User)
        .join(User, User.id == PingRecipient.user_id)
        .where(PingRecipient.ping_id == ping_id)
        .order_by(User.name)).all()
    return [{"user_id": u.id, "name": u.name, "email": u.email,
             "read_at": r.read_at, "completed_at": r.completed_at}
            for r, u in rows]


def _serialize_recipient(r: dict) -> dict:
    return {**r, "read_at": _iso(r["read_at"]), "completed_at": _iso(r["completed_at"])}


def _request_summary(viewer, request_id: str | None) -> dict | None:
    """Identifying summary of the request a ping is about (spec section 4.1).

    It renders even when the viewer cannot open the request; only `visible`
    says whether the deep link should render too -- a link that 403s reads as
    broken software (spec section 5).
    """
    if request_id is None:
        return None
    req = db.session.get(CapexRequest, request_id)
    if req is None:
        return None
    return {
        "id": req.id,
        "number": req.number,
        "status": req.status,
        "division_name": (f"{req.division.number} — {req.division.name}"
                          if req.division else None),
        "requestor_name": req.requestor.name if req.requestor else None,
        "total_cost": money_str(req.total_cost),
        "visible": request_service.can_view(req, viewer),
    }


def _summarize(ping: Ping, viewer) -> dict:
    # created_at first, id as a deterministic tiebreaker -- ids are uuid4().hex,
    # NOT monotonic, and cannot order by recency alone.
    replies = db.session.scalars(
        select(Ping).where(Ping.parent_id == ping.id)
        .order_by(Ping.created_at, Ping.id)).all()
    roster = _roster(ping.id)
    mine = next((r for r in roster if r["user_id"] == viewer.id), None)
    unread_replies = db.session.scalar(
        select(func.count(PingRecipient.id))
        .join(Ping, Ping.id == PingRecipient.ping_id)
        .where(Ping.parent_id == ping.id,
               PingRecipient.user_id == viewer.id,
               PingRecipient.read_at.is_(None))) or 0
    sender = db.session.get(User, ping.sender_id)
    # unread_for_me folds in unread REPLIES, not just the root row: a reply the
    # viewer has not opened must still bold the bell and the card, or the
    # summary disagrees with what unread_count (and the bell) already count.
    unread_for_me = bool(mine and mine["read_at"] is None) or unread_replies > 0
    last = replies[-1] if replies else ping
    payload = {
        "id": ping.id,
        "note": ping.note,
        "sender": {"id": sender.id, "name": sender.name},
        "created_at": _iso(ping.created_at),
        "request_id": ping.request_id,
        "request": _request_summary(viewer, ping.request_id),
        "recipients": [_serialize_recipient(r) for r in roster],
        "reply_count": len(replies),
        "unread_replies": unread_replies,
        "unread_for_me": unread_for_me,
        "last_activity_id": last.id,
        "last_activity_at": _iso(last.created_at),
        # Every reply's text, so the panel's search reaches a phrase said only
        # in a reply. The replies are already loaded above: no new query.
        "search_blob": " ".join(r.note for r in replies),
    }
    return apply_shared_done(payload, roster)


def list_pings(viewer, box: str) -> list[dict]:
    """Conversation roots only, newest activity first, capped at 200.

    A conversation the viewer STARTED returns to their inbox once someone
    replies: that reply is addressed to them, and the inbox is where they look
    for it. `sent` stays "exchanges I opened", so an answered ping is in both.
    """
    if box not in ("inbox", "sent"):
        raise ServiceError("box must be 'inbox' or 'sent'.", 400)

    if box == "sent":
        stmt = select(Ping).where(Ping.parent_id.is_(None),
                                  Ping.sender_id == viewer.id)
    else:
        addressed = (
            select(Ping.id)
            .join(PingRecipient, PingRecipient.ping_id == Ping.id)
            .where(PingRecipient.user_id == viewer.id))
        # A root is in my inbox if I am on the root OR on any of its replies.
        roots_via_replies = (
            select(Ping.parent_id).where(Ping.id.in_(addressed),
                                         Ping.parent_id.is_not(None)))
        stmt = select(Ping).where(
            Ping.parent_id.is_(None),
            Ping.id.in_(addressed.union(roots_via_replies)))

    roots = db.session.scalars(stmt).all()
    out = [_summarize(p, viewer) for p in roots]
    out.sort(key=lambda p: (p["last_activity_at"], p["last_activity_id"]),
             reverse=True)
    return out[:200]


def _may_see(viewer, ping: Ping) -> bool:
    """Membership is the WHOLE thread, not just the root.

    list_pings's roots_via_replies puts a root in someone's inbox when they are
    addressed only on a REPLY, never on the root itself -- so this must agree,
    or the inbox lists a conversation the detail view then refuses. Membership
    is: the root's sender, the root's recipients, every reply's sender, and
    every reply's recipients.
    """
    ping_ids = [ping.id] + list(db.session.scalars(
        select(Ping.id).where(Ping.parent_id == ping.id)).all())
    if db.session.scalar(
        select(func.count(Ping.id))
        .where(Ping.id.in_(ping_ids), Ping.sender_id == viewer.id)) > 0:
        return True
    return db.session.scalar(
        select(func.count(PingRecipient.id))
        .where(PingRecipient.ping_id.in_(ping_ids),
               PingRecipient.user_id == viewer.id)) > 0


def unread_count(viewer) -> int:
    return db.session.scalar(
        select(func.count(PingRecipient.id))
        .where(PingRecipient.user_id == viewer.id,
               PingRecipient.read_at.is_(None))) or 0


def _stamp_read(viewer, ping_ids: list[str]) -> None:
    """Stamp only THIS viewer's rows. Read is personal."""
    rows = db.session.scalars(
        select(PingRecipient).where(PingRecipient.ping_id.in_(ping_ids),
                                    PingRecipient.user_id == viewer.id,
                                    PingRecipient.read_at.is_(None))).all()
    if not rows:
        return
    now = datetime.now(timezone.utc)
    for row in rows:
        row.read_at = now
    db.session.commit()


def get_ping(viewer, ping_id: str) -> dict:
    ping = db.session.get(Ping, ping_id)
    if ping is None or ping.parent_id is not None:
        raise ServiceError("No such ping.", 404)
    if not _may_see(viewer, ping):
        raise ServiceError("Forbidden.", 403)

    replies = db.session.scalars(
        select(Ping).where(Ping.parent_id == ping.id)
        .order_by(Ping.created_at, Ping.id)).all()
    _stamp_read(viewer, [ping.id] + [r.id for r in replies])

    payload = _summarize(ping, viewer)
    payload["replies"] = [
        {"id": r.id, "note": r.note, "created_at": _iso(r.created_at),
         "sender": {"id": r.sender_id,
                    "name": db.session.get(User, r.sender_id).name}}
        for r in replies]
    return payload
