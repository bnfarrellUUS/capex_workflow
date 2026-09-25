"""Saving an approver pool in the order an admin set.

The pools (division L1, region VPs, threshold L3) are many-to-many
relationships whose rows carry a `position`. SQLAlchemy's `secondary`
relationship writes only the two foreign keys, so the order is written here
after the rows exist, and the relationship reads it back via `order_by`.
"""

from sqlalchemy import bindparam

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
    if users:
        rel = type(owner).__mapper__.relationships[attr]
        # The relationship knows which association columns point at the owner
        # and at the user; guessing by column name would pick the wrong one
        # if the table ever grew another column.
        (_, owner_col), = rel.synchronize_pairs
        (_, user_col), = rel.secondary_synchronize_pairs
        db.session.execute(
            rel.secondary.update()
            .where(owner_col == bindparam("b_owner"), user_col == bindparam("b_user"))
            .values(position=bindparam("b_position")),
            [{"b_owner": owner.id, "b_user": u.id, "b_position": i}
             for i, u in enumerate(users)])
    # Drop the in-memory list so the next read comes back ordered from the DB.
    db.session.expire(owner, [attr])
