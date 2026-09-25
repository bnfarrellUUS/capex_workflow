from app.extensions import db
from app.models import Region
from app.services.approver_pools import set_pool
from app.services.errors import ServiceError


def list_regions():
    return db.session.query(Region).order_by(Region.name).all()


def create_region(*, name, active=True, vp_approver_ids=None):
    nm = name.strip()
    if db.session.query(Region).filter_by(name=nm).first() is not None:
        raise ServiceError("Region name already exists.", 409)
    region = Region(name=nm, active=active)
    db.session.add(region)
    set_pool(region, "vp_approvers", vp_approver_ids)
    db.session.commit()
    return region


def update_region(region_id, *, name, active, vp_approver_ids):
    region = db.session.get(Region, region_id)
    if region is None:
        raise ServiceError("Region not found.", 404)
    nm = name.strip()
    clash = db.session.query(Region).filter(
        Region.name == nm, Region.id != region_id).first()
    if clash is not None:
        raise ServiceError("Region name already exists.", 409)
    region.name = nm
    region.active = active
    set_pool(region, "vp_approvers", vp_approver_ids)
    db.session.commit()
    return region
