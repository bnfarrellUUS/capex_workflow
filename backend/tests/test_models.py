from decimal import Decimal

import pytest

from app.extensions import db
from app.models import (
    User, Division, CapexRequest, EquipmentItem,
)


def test_user_division_relationship(app):
    div = Division(number="100", name="Field Services")
    user = User(username="jdoe", email="jdoe@x.com", name="J Doe", password_hash="x", division=div)
    db.session.add_all([div, user])
    db.session.commit()
    assert user.division.name == "Field Services"
    assert div.users[0].username == "jdoe"


def test_roles_default_is_requestor(app):
    user = User(username="a", email="a@x.com", name="A", password_hash="x")
    db.session.add(user)
    db.session.commit()
    assert user.roles == '["REQUESTOR"]'


def test_self_referential_delegate(app):
    a = User(username="a", email="a@x.com", name="A", password_hash="x")
    b = User(username="b", email="b@x.com", name="B", password_hash="x")
    a.delegate = b
    db.session.add_all([a, b])
    db.session.commit()
    assert a.delegate.username == "b"
    assert b.delegates_for[0].username == "a"


def test_equipment_items_cascade_delete(app):
    req = CapexRequest(number="CX000001", requestor_id=_make_user(app).id)
    req.equipment_items.append(
        EquipmentItem(units=1, condition="NEW", type="Truck", make="Ford", model="F150", cost=Decimal("50000"))
    )
    db.session.add(req)
    db.session.commit()
    assert db.session.query(EquipmentItem).count() == 1
    db.session.delete(req)
    db.session.commit()
    assert db.session.query(EquipmentItem).count() == 0


def _make_user(app):
    u = User(username="r", email="r@x.com", name="R", password_hash="x")
    db.session.add(u)
    db.session.commit()
    return u


def test_must_change_password_defaults_false(app):
    u = User(username="flaguser", email="flag@x.com", name="F",
             password_hash="x")
    db.session.add(u)
    db.session.commit()
    assert u.must_change_password is False


def test_default_password_config(app):
    assert app.config["DEFAULT_PASSWORD"] == "Welcome@1"
