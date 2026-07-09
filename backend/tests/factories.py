from decimal import Decimal

from app.extensions import db
from app.models import User, Division, CapexRequest, EquipmentItem
from app.services import threshold_service
from app.services.security import hash_password


def make_user(username, roles='["APPROVER"]', delegate_id=None):
    u = User(username=username, email=f"{username}@x.com", name=username.title(),
             password_hash=hash_password("secret123"), roles=roles, delegate_id=delegate_id)
    db.session.add(u)
    db.session.commit()
    return u


def make_division(number="100", l1_approver_id=None):
    d = Division(number=number, name="Field Services", l1_approver_id=l1_approver_id)
    db.session.add(d)
    db.session.commit()
    return d


def set_thresholds(l1="50000", l2="250000", l2_approver=None, l3_approver=None):
    rows = {t.level: t for t in threshold_service.list_thresholds()}
    rows[1].max_amount = Decimal(l1)
    rows[2].max_amount = Decimal(l2)
    rows[2].approver_id = l2_approver
    rows[3].max_amount = None
    rows[3].approver_id = l3_approver
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
