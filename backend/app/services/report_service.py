"""Year-based reporting aggregates for the Reports page.

Computed in Python rather than dialect-specific SQL: annual request volumes
are small for this internal tool, and this sidesteps SQLite-vs-Azure-SQL
date-function differences while staying easy to unit test.
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models import CapexRequest
from app.serialization import money_str

STATUS_ORDER = ("DRAFT", "PENDING_L1", "PENDING_L2", "PENDING_L3",
                "APPROVED", "REJECTED")
_PENDING = ("PENDING_L1", "PENDING_L2", "PENDING_L3")


def _bucket():
    return {"approved_total": Decimal(0), "approved_count": 0,
            "pending_total": Decimal(0), "pending_count": 0}


def _tally(bucket, req):
    cost = req.total_cost or Decimal(0)
    if req.status == "APPROVED":
        bucket["approved_total"] += cost
        bucket["approved_count"] += 1
    elif req.status in _PENDING:
        bucket["pending_total"] += cost
        bucket["pending_count"] += 1


def _out(bucket):
    return {**bucket,
            "approved_total": money_str(bucket["approved_total"]),
            "pending_total": money_str(bucket["pending_total"])}


def _cycle_days(req):
    submitted = min((a.created_at for a in req.actions
                     if a.action == "SUBMITTED" and a.created_at), default=None)
    approved = max((a.created_at for a in req.actions
                    if a.action == "APPROVED" and a.created_at), default=None)
    if submitted is None or approved is None:
        return None
    return (approved - submitted).total_seconds() / 86400.0


def summary(year=None):
    rows = db.session.query(CapexRequest).all()
    year = int(year) if year else datetime.now(timezone.utc).year
    years = sorted({r.request_date.year for r in rows if r.request_date}
                   | {year}, reverse=True)
    in_year = [r for r in rows
               if r.request_date and r.request_date.year == year]

    totals = _bucket()
    by_division = {}
    by_month = {m: _bucket() for m in range(1, 13)}
    by_status = {s: {"count": 0, "total": Decimal(0)} for s in STATUS_ORDER}

    for r in in_year:
        _tally(totals, r)
        div = (f"{r.division.number} — {r.division.name}"
               if r.division else "—")
        _tally(by_division.setdefault(div, _bucket()), r)
        _tally(by_month[r.request_date.month], r)
        st = by_status.setdefault(r.status, {"count": 0, "total": Decimal(0)})
        st["count"] += 1
        st["total"] += r.total_cost or Decimal(0)

    cycle = [d for d in (_cycle_days(r) for r in in_year
                         if r.status == "APPROVED") if d is not None]

    return {
        "year": year,
        "years": years,
        "totals": {**_out(totals), "request_count": len(in_year)},
        "by_division": [{"division": name, **_out(b)}
                        for name, b in sorted(by_division.items())],
        "by_month": [{"month": m, **_out(b)} for m, b in by_month.items()],
        "by_status": [{"status": s, "count": v["count"],
                       "total": money_str(v["total"])}
                      for s, v in by_status.items()],
        "cycle_time": {
            "avg_days": round(sum(cycle) / len(cycle), 1) if cycle else None,
            "count": len(cycle)},
    }
