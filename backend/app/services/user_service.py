from app.extensions import db
from app.models import User
from app.roles import serialize_roles, valid_roles
from app.services.errors import ServiceError
from app.services.security import hash_password


def list_users():
    return db.session.query(User).order_by(User.username).all()


def create_user(*, username, email, name, password, roles, division_id):
    if not valid_roles(roles):
        raise ServiceError("Invalid role.")
    uname = username.strip().lower()
    mail = email.strip().lower()
    clash = db.session.query(User).filter(
        (User.username == uname) | (User.email == mail)
    ).first()
    if clash is not None:
        raise ServiceError("Username or email already exists.", 409)
    user = User(
        username=uname, email=mail, name=name.strip(),
        password_hash=hash_password(password),
        roles=serialize_roles(roles), division_id=division_id or None,
    )
    db.session.add(user)
    db.session.commit()
    return user


def update_user(user_id, *, name, email, roles, division_id, active):
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", 404)
    if not valid_roles(roles):
        raise ServiceError("Invalid role.")
    mail = email.strip().lower()
    clash = db.session.query(User).filter(User.email == mail, User.id != user_id).first()
    if clash is not None:
        raise ServiceError("Email already in use.", 409)
    user.name = name.strip()
    user.email = mail
    user.roles = serialize_roles(roles)
    user.division_id = division_id or None
    user.active = active
    db.session.commit()
    return user


def admin_reset_password(user_id, password):
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", 404)
    user.password_hash = hash_password(password)
    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()
    return user
