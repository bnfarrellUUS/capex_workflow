from decimal import Decimal

from app.extensions import db
from app.models import User, Division, CapexRequest, EquipmentItem
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


def make_division(number="100", l1_approver_id=None, l1_approver_ids=None):
    d = Division(number=number, name="Field Services")
    d.l1_approvers = _users(l1_approver_ids if l1_approver_ids is not None else [l1_approver_id])
    db.session.add(d)
    db.session.commit()
    return d


def set_thresholds(l1="50000", l2="250000", l2_approver=None, l3_approver=None,
                   l2_approvers=None, l3_approvers=None):
    rows = {t.level: t for t in threshold_service.list_thresholds()}
    rows[1].max_amount = Decimal(l1)
    rows[2].max_amount = Decimal(l2)
    rows[2].approvers = _users(l2_approvers if l2_approvers is not None else [l2_approver])
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
