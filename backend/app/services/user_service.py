from app.extensions import db
from app.models import (
    User, CapexRequest, ApprovalAction, Attachment,
    division_l1_approvers, threshold_approvers,
)
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


def update_user(user_id, *, name, email, roles, division_id, active, username=None):
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", 404)
    if not valid_roles(roles):
        raise ServiceError("Invalid role.")
    mail = email.strip().lower()
    clash = db.session.query(User).filter(User.email == mail, User.id != user_id).first()
    if clash is not None:
        raise ServiceError("Email already in use.", 409)
    if username is not None:
        uname = username.strip().lower()
        if not uname:
            raise ServiceError("Username cannot be empty.")
        taken = db.session.query(User).filter(User.username == uname, User.id != user_id).first()
        if taken is not None:
            raise ServiceError("Username already in use.", 409)
        user.username = uname
    user.name = name.strip()
    user.email = mail
    user.roles = serialize_roles(roles)
    user.division_id = division_id or None
    user.active = active
    db.session.commit()
    return user


def delete_user(user_id, actor_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", 404)
    if user_id == actor_id:
        raise ServiceError("You can't delete your own account.")
    # Preserve the audit trail: refuse if the user is tied to any request,
    # approval action, or attachment. Deactivate such users instead.
    referenced = (
        db.session.query(CapexRequest.id).filter(
            (CapexRequest.requestor_id == user_id) | (CapexRequest.assignee_id == user_id)).first()
        or db.session.query(ApprovalAction.id).filter(
            (ApprovalAction.actor_id == user_id) | (ApprovalAction.acted_for_id == user_id)).first()
        or db.session.query(Attachment.id).filter(Attachment.uploaded_by_id == user_id).first()
    )
    if referenced is not None:
        raise ServiceError(
            "This user has request or approval history and can't be deleted. "
            "Deactivate them instead.", 409)
    # Detach safe references so the delete doesn't violate foreign keys.
    db.session.query(User).filter(User.delegate_id == user_id).update({"delegate_id": None})
    db.session.execute(division_l1_approvers.delete().where(division_l1_approvers.c.user_id == user_id))
    db.session.execute(threshold_approvers.delete().where(threshold_approvers.c.user_id == user_id))
    db.session.delete(user)
    db.session.commit()


def admin_reset_password(user_id, password):
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", 404)
    user.password_hash = hash_password(password)
    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()
    return user
