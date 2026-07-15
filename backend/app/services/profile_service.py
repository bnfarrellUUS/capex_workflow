from app.extensions import db
from app.models import User
from app.services.errors import ServiceError
from app.services.security import verify_password, hash_password


def change_password(user_id, current, new):
    user = db.session.get(User, user_id)
    if not verify_password(current, user.password_hash):
        raise ServiceError("Current password is incorrect.")
    user.password_hash = hash_password(new)
    user.must_change_password = False
    db.session.commit()


def set_delegate(user_id, delegate_id):
    user = db.session.get(User, user_id)
    if delegate_id:
        if delegate_id == user_id:
            raise ServiceError("You cannot delegate to yourself.")
        if db.session.get(User, delegate_id) is None:
            raise ServiceError("Delegate not found.", 404)
    user.delegate_id = delegate_id or None
    db.session.commit()
    return user


def delegate_options(user_id):
    users = db.session.query(User).filter(User.active.is_(True), User.id != user_id).all()
    return [u for u in users if "APPROVER" in u.roles_list]
