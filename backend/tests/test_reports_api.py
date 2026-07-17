from datetime import datetime
from decimal import Decimal

from app.extensions import db
from app.models import CapexRequest
from tests.factories import make_user


def _login(client, user):
    client.post("/api/auth/login",
                json={"email": user.email, "password": "secret123"})


def test_summary_requires_login(client, app):
    assert client.get("/api/reports/summary").status_code == 401


def test_summary_forbidden_for_requestor_and_approver(client, app):
    for key, roles in (("r", '["REQUESTOR"]'), ("ap", '["APPROVER"]')):
        u = make_user(key, roles=roles)
        _login(client, u)
        assert client.get("/api/reports/summary").status_code == 403


def test_summary_ok_for_finance_and_admin(client, app):
    u = make_user("fin", roles='["FINANCE"]')
    r = CapexRequest(number="CX000001", requestor_id=u.id, status="APPROVED",
                     total_cost=Decimal("1000"),
                     request_date=datetime(2026, 4, 1))
    db.session.add(r)
    db.session.commit()

    _login(client, u)
    body = client.get("/api/reports/summary?year=2026").get_json()
    assert body["year"] == 2026
    assert body["totals"]["approved_total"] == "1000"
    assert {"year", "years", "totals", "by_division", "by_month",
            "by_status", "cycle_time"} <= set(body)

    admin = make_user("adm", roles='["ADMIN"]')
    _login(client, admin)
    assert client.get("/api/reports/summary").status_code == 200
