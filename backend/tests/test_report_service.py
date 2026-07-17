from datetime import datetime
from decimal import Decimal

from app.extensions import db
from app.models import CapexRequest, ApprovalAction
from app.services import report_service
from tests.factories import make_user, make_division

_seq = 0


def _req(user, division=None, status="DRAFT", total="0",
         when=datetime(2026, 3, 5)):
    global _seq
    _seq += 1
    r = CapexRequest(
        number=f"CX{_seq:06d}", requestor_id=user.id,
        division_id=division.id if division else None,
        status=status, total_cost=Decimal(total), request_date=when)
    db.session.add(r)
    db.session.commit()
    return r


def _action(req, user, action, when, level=1):
    db.session.add(ApprovalAction(
        request_id=req.id, actor_id=user.id, action=action,
        level=level, created_at=when))
    db.session.commit()


def test_summary_splits_approved_vs_pending_by_division(app):
    u = make_user("u", roles='["REQUESTOR"]')
    d1 = make_division(number="100")
    d2 = make_division(number="200")
    _req(u, d1, status="APPROVED", total="1000")
    _req(u, d1, status="PENDING_L1", total="500")
    _req(u, d2, status="APPROVED", total="2000")
    _req(u, d2, status="REJECTED", total="9999")   # excluded from spend

    s = report_service.summary(2026)
    assert s["year"] == 2026
    assert s["totals"]["approved_total"] == "3000"
    assert s["totals"]["approved_count"] == 2
    assert s["totals"]["pending_total"] == "500"
    assert s["totals"]["pending_count"] == 1
    assert s["totals"]["request_count"] == 4

    div1 = next(r for r in s["by_division"] if r["division"].startswith("100"))
    assert div1["approved_total"] == "1000"
    assert div1["pending_total"] == "500"
    div2 = next(r for r in s["by_division"] if r["division"].startswith("200"))
    assert div2["approved_total"] == "2000"
    assert div2["pending_total"] == "0"


def test_summary_buckets_months_and_handles_no_division(app):
    u = make_user("u", roles='["REQUESTOR"]')
    _req(u, None, status="APPROVED", total="100", when=datetime(2026, 1, 10))
    _req(u, None, status="APPROVED", total="200", when=datetime(2026, 11, 3))

    s = report_service.summary(2026)
    assert len(s["by_month"]) == 12
    assert s["by_month"][0]["month"] == 1
    assert s["by_month"][0]["approved_total"] == "100"
    assert s["by_month"][10]["approved_total"] == "200"
    assert s["by_month"][5]["approved_total"] == "0"
    assert s["by_division"] == [{
        "division": "—", "approved_total": "300", "approved_count": 2,
        "pending_total": "0", "pending_count": 0}]


def test_summary_by_status_workflow_order_includes_drafts(app):
    u = make_user("u", roles='["REQUESTOR"]')
    _req(u, status="DRAFT", total="50")
    _req(u, status="APPROVED", total="70")
    s = report_service.summary(2026)
    statuses = [r["status"] for r in s["by_status"]]
    assert statuses == ["DRAFT", "PENDING_L1", "PENDING_L2", "PENDING_L3",
                        "APPROVED", "REJECTED"]
    draft = s["by_status"][0]
    assert draft["count"] == 1 and draft["total"] == "50"


def test_summary_excludes_other_years_but_lists_them(app):
    u = make_user("u", roles='["REQUESTOR"]')
    _req(u, status="APPROVED", total="100", when=datetime(2025, 6, 1))
    _req(u, status="APPROVED", total="200", when=datetime(2026, 6, 1))
    s = report_service.summary(2026)
    assert s["totals"]["approved_total"] == "200"
    assert s["years"] == [2026, 2025]


def test_cycle_time_first_submit_to_last_approve(app):
    u = make_user("u", roles='["REQUESTOR"]')
    r = _req(u, status="APPROVED", total="100")
    _action(r, u, "SUBMITTED", datetime(2026, 3, 1))
    _action(r, u, "APPROVED", datetime(2026, 3, 2), level=1)
    _action(r, u, "APPROVED", datetime(2026, 3, 4), level=2)
    never = _req(u, status="PENDING_L1", total="100")
    _action(never, u, "SUBMITTED", datetime(2026, 3, 1))

    s = report_service.summary(2026)
    assert s["cycle_time"] == {"avg_days": 3.0, "count": 1}


def test_summary_empty_year_returns_zeroes(app):
    s = report_service.summary(2030)
    assert s["totals"]["request_count"] == 0
    assert s["totals"]["approved_total"] == "0"
    assert s["cycle_time"] == {"avg_days": None, "count": 0}
    assert 2030 in s["years"]
    assert len(s["by_month"]) == 12
    assert len(s["by_status"]) == 6
