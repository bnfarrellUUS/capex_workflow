from app.extensions import db
from app.models import Division
from app.services.errors import ServiceError


def list_divisions():
    return db.session.query(Division).order_by(Division.number).all()


def create_division(*, number, name):
    num = number.strip()
    if db.session.query(Division).filter_by(number=num).first() is not None:
        raise ServiceError("Division number already exists.", 409)
    div = Division(number=num, name=name.strip())
    db.session.add(div)
    db.session.commit()
    return div


def update_division(division_id, *, number, name, active, l1_approver_id):
    div = db.session.get(Division, division_id)
    if div is None:
        raise ServiceError("Division not found.", 404)
    num = number.strip()
    clash = db.session.query(Division).filter(
        Division.number == num, Division.id != division_id
    ).first()
    if clash is not None:
        raise ServiceError("Division number already exists.", 409)
    div.number = num
    div.name = name.strip()
    div.active = active
    div.l1_approver_id = l1_approver_id or None
    db.session.commit()
    return div
