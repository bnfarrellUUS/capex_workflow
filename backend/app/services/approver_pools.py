"""Saving an approver pool in the order an admin set.

The pools (division L1, region VPs, threshold L3) are many-to-many
relationships whose rows carry a `position`. SQLAlchemy's `secondary`
relationship writes only the two foreign keys, so the order is written here
after the rows exist, and the relationship reads it back via `order_by`.
"""

from app.extensions import db
from app.models import User


def ordered_users(ids):
    """Users for `ids` in the order given; blanks, duplicates and unknown ids
    are dropped without disturbing the rest."""
    wanted = list(dict.fromkeys(i for i in (ids or []) if i))
    if not wanted:
        return []
    by_id = {u.id: u for u in db.session.query(User).filter(User.id.in_(wanted))}
    return [by_id[i] for i in wanted if i in by_id]


def set_pool(owner, attr, user_ids):
    """Replace `owner.<attr>` with `user_ids`, keeping their order. Flushes, so
    `owner` must already be in the session; the caller commits."""
    users = ordered_users(user_ids)
    setattr(owner, attr, users)
    db.session.flush()
    table = type(owner).__mapper__.relationships[attr].secondary
    owner_col = next(c for c in table.c if c.name not in ("user_id", "position"))
    for position, user in enumerate(users):
        db.session.execute(
            table.update()
            .where(owner_col == owner.id, table.c.user_id == user.id)
            .values(position=position))
    # Drop the in-memory list so the next read comes back ordered from the DB.
    db.session.expire(owner, [attr])
