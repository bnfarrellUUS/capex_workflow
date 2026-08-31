from decimal import Decimal

from app.extensions import db
from app.models import User, Division, Region, CapexRequest, EquipmentItem
from app.services import threshold_service
from app.services.security import hash_password


def make_user(key, roles='["APPROVER"]', delegate_id=None):
    u = User(email=f"{key}@x.com", name=key.title(),
             password_hash=hash_password("secret123"), roles=roles, delegate_id=delegate_id)
    db.session.add(u)
    db.session.commit()
    return u


def _users(ids):
    ids = [i for i in ids if i]
    return db.session.query(User).filter(User.id.in_(ids)).all() if ids else []


_DEFAULT_REGION_NAME = "Test Region"


def _default_region():
    return db.session.query(Region).filter_by(name=_DEFAULT_REGION_NAME).one_or_none()


def make_region(name=_DEFAULT_REGION_NAME, vp_ids=None):
    r = Region(name=name)
    r.vp_approvers = _users(vp_ids or [])
    db.session.add(r)
    db.session.commit()
    return r


def make_division(number="100", l1_approver_id=None, l1_approver_ids=None, region=None):
    d = Division(number=number, name="Field Services")
    d.l1_approvers = _users(l1_approver_ids if l1_approver_ids is not None else [l1_approver_id])
    d.region = region if region is not None else _default_region()
    db.session.add(d)
    db.session.commit()
    return d


def set_thresholds(l1="50000", l2="250000", l2_approver=None, l3_approver=None,
                   l2_approvers=None, l3_approvers=None):
    rows = {t.level: t for t in threshold_service.list_thresholds()}
    rows[1].max_amount = Decimal(l1)
    rows[2].max_amount = Decimal(l2)
    # L2 approvers live on a region now. Keep this factory's signature: route
    # the given users into a shared default region and attach it to every
    # division that doesn't have one yet (make_division picks it up too, so
    # either call order works).
    region = _default_region() or Region(name=_DEFAULT_REGION_NAME)
    region.vp_approvers = _users(l2_approvers if l2_approvers is not None else [l2_approver])
    db.session.add(region)
    for d in db.session.query(Division).all():
        if d.region_id is None:
            d.region = region
    rows[3].max_amount = None
    rows[3].approvers = _users(l3_approvers if l3_approvers is not None else [l3_approver])
    db.session.commit()
    return list(rows.values())


def make_draft(requestor_id, division_id, costs=("30000",), number="CX000001"):
    r = CapexRequest(number=number, requestor_id=requestor_id, division_id=division_id,
                     description="Desc", justification="Just", effect_on_operations="Ops")
    for c in costs:
        r.equipment_items.append(EquipmentItem(units=1, condition="NEW", type="T",
                                               make="M", model="Mo", cost=Decimal(c)))
    db.session.add(r)
    db.session.commit()
    return r
