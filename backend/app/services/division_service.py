from app.extensions import db
from app.models import Division
from app.services.approver_pools import set_pool
from app.services.errors import ServiceError


def _region(region_id):
    if not region_id:
        return None
    from app.models import Region
    region = db.session.get(Region, region_id)
    if region is None:
        raise ServiceError("Region not found.", 400)
    return region


def list_divisions():
    return db.session.query(Division).order_by(Division.number).all()


def create_division(*, number, name, region_id=None):
    num = number.strip()
    if db.session.query(Division).filter_by(number=num).first() is not None:
        raise ServiceError("Division number already exists.", 409)
    div = Division(number=num, name=name.strip())
    div.region = _region(region_id)
    db.session.add(div)
    db.session.commit()
    return div


def update_division(division_id, *, number, name, active, l1_approver_ids, region_id=None):
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
    set_pool(div, "l1_approvers", l1_approver_ids)
    div.region = _region(region_id)
    db.session.commit()
    return div
