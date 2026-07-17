# Exports & Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Excel export of the (filtered) requests list for all users, plus a FINANCE/ADMIN-only Reports page (year picker; spend by division/month/status; cycle time), per `docs/superpowers/specs/2026-07-17-exports-reporting-design.md`.

**Architecture:** Server-side xlsx generation (openpyxl) behind `GET /api/requests/export.xlsx`, reusing `request_service.list_requests` for visibility plus a server-side `q` search. A new `reports` blueprint (`GET /api/reports/summary?year=`) aggregates one calendar year of requests **in Python** (small volumes; avoids SQLite-vs-Azure-SQL dialect risk). Frontend: an Export button + "All" scope tab on the requests list, and a new `/reports` page (BrandCard, tables + CSS bars, no chart library).

**Tech Stack:** Flask + SQLAlchemy 2.0, openpyxl (new dep), Pydantic untouched (no new writable fields). React 19 + TanStack Query 5 + Tailwind v4, vitest.

## Global Constraints

- Repo path contains `&` — run frontend tooling via node directly:
  `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`,
  `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/vite/bin/vite.js build`.
- Backend tests: `cd backend && pytest -q` (venv at `backend/.venv`; if `pytest` is not on PATH use `.venv/Scripts/python -m pytest`).
- Routes stay thin; logic in `services/`; handled API errors raise `ServiceError(msg, status)`.
- Money serializes through `app/serialization.py::money_str` (string, no trailing zeros).
- Prefer semantic Tailwind tokens (`bg`, `surface`, `surface-2`, `border`, `fg`, `muted`, `accent`) over `slate-*`. Data-table `thead` uses `bg-brand-sky/25 text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky` uppercase `text-xs`.
- One focused git commit per task, message style matching repo history (`area: what changed`), ending with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Do NOT add fields to `RequestDraft`/`FinanceIn` schemas — this feature adds no writable fields.

---

### Task 1: Export service (openpyxl workbook + search filter)

**Files:**
- Modify: `backend/requirements.txt` (add openpyxl)
- Create: `backend/app/services/export_service.py`
- Test: `backend/tests/test_export_service.py`

**Interfaces:**
- Consumes: `request_service.list_requests(viewer, scope, status, division_id)` (existing).
- Produces: `export_service.export_xlsx(viewer, scope="mine", status=None, division_id=None, q=None) -> bytes`, `export_service.matches_query(req, q) -> bool`, `export_service.COLUMNS` (list of `(header, getter, kind)`).

- [ ] **Step 1: Add the dependency**

Append to `backend/requirements.txt` (after `pywin32` line, before `pytest`):

```
openpyxl>=3.1
```

Run: `cd backend && .venv/Scripts/pip install -r requirements.txt`
Expected: `Successfully installed openpyxl-3.1.x` (or already satisfied).

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_export_service.py`:

```python
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from openpyxl import load_workbook

from app.extensions import db
from app.services import export_service
from tests.factories import make_user, make_division, make_draft


def _ns_req(number="CX000001", division=None, requestor="Alice"):
    return SimpleNamespace(
        number=number,
        division=division,
        requestor=SimpleNamespace(name=requestor) if requestor else None,
    )


def test_matches_query_blank_matches_everything():
    assert export_service.matches_query(_ns_req(), None)
    assert export_service.matches_query(_ns_req(), "   ")


def test_matches_query_number_division_requestor_case_insensitive():
    div = SimpleNamespace(number="200", name="Field Services")
    req = _ns_req(number="CX000042", division=div, requestor="Bob Smith")
    assert export_service.matches_query(req, "cx0000")
    assert export_service.matches_query(req, "field serv")
    assert export_service.matches_query(req, "200 — field")
    assert export_service.matches_query(req, "bob")
    assert not export_service.matches_query(req, "zzz")


def test_matches_query_handles_missing_division_and_requestor():
    req = _ns_req(division=None, requestor=None)
    assert export_service.matches_query(req, "cx000001")
    assert not export_service.matches_query(req, "field")


def test_build_workbook_headers_and_types(app):
    user = make_user("req", roles='["REQUESTOR"]')
    div = make_division()
    r = make_draft(user.id, div.id, number="CX000009")
    r.total_cost = Decimal("30000")
    r.request_date = datetime(2026, 3, 5)
    r.budgeted = True
    r.cost_machinery = Decimal("12345.67")
    db.session.commit()

    data = export_service.export_xlsx(user, scope="mine")
    ws = load_workbook(BytesIO(data)).active

    headers = [c.value for c in ws[1]]
    assert headers[:6] == ["Number", "Status", "Division", "Requestor",
                           "Request Date", "Total Cost"]
    assert "Cost: Machinery & Equipment" in headers
    assert "Finance Completed" in headers

    row = list(ws[2])
    by_header = dict(zip(headers, row))
    assert by_header["Number"].value == "CX000009"
    assert by_header["Division"].value == "100 — Field Services"
    assert float(by_header["Total Cost"].value) == 30000.0
    assert by_header["Total Cost"].number_format == '"$"#,##0.00'
    assert by_header["Request Date"].value.year == 2026
    assert by_header["Budgeted"].value == "Yes"
    assert by_header["Replacement"].value == "No"
    assert float(by_header["Cost: Machinery & Equipment"].value) == 12345.67


def test_export_xlsx_filters_by_query_and_sorts_by_number(app):
    user = make_user("req", roles='["REQUESTOR"]')
    div = make_division()
    make_draft(user.id, div.id, number="CX000002")
    make_draft(user.id, div.id, number="CX000001")
    data = export_service.export_xlsx(user, scope="mine")
    ws = load_workbook(BytesIO(data)).active
    numbers = [row[0].value for row in ws.iter_rows(min_row=2)]
    assert numbers == ["CX000001", "CX000002"]

    data = export_service.export_xlsx(user, scope="mine", q="CX000002")
    ws = load_workbook(BytesIO(data)).active
    numbers = [row[0].value for row in ws.iter_rows(min_row=2)]
    assert numbers == ["CX000002"]


def test_export_xlsx_empty_is_valid_workbook_with_header(app):
    user = make_user("req", roles='["REQUESTOR"]')
    data = export_service.export_xlsx(user, scope="mine")
    ws = load_workbook(BytesIO(data)).active
    assert ws[1][0].value == "Number"
    assert list(ws.iter_rows(min_row=2)) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_export_service.py -q`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named 'app.services.export_service'` (import error counts as the failing state).

- [ ] **Step 4: Write the implementation**

Create `backend/app/services/export_service.py`:

```python
"""Excel export of the requests list (openpyxl).

Visibility comes from request_service.list_requests; `q` replicates the
client-side list search so the file matches the filtered screen.
"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.services import request_service

_HEADER_FILL = PatternFill("solid", start_color="0B2A4A")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_MONEY_FMT = '"$"#,##0.00'
_DATE_FMT = "yyyy-mm-dd"


def _division_name(req):
    return f"{req.division.number} — {req.division.name}" if req.division else None


def _yn(value):
    return "Yes" if value else "No"


def _day(value):
    # Excel can't store tz-aware datetimes; the date is all we report anyway.
    return value.date() if value else None


def matches_query(req, q):
    """Case-insensitive contains over number, division display name, and
    requestor name — same fields as the frontend list search."""
    if not q or not q.strip():
        return True
    needle = q.strip().lower()
    fields = (req.number, _division_name(req),
              req.requestor.name if req.requestor else None)
    return any(needle in f.lower() for f in fields if f)


# (header, getter, kind); kind picks the cell number format.
COLUMNS = [
    ("Number", lambda r: r.number, "text"),
    ("Status", lambda r: r.status, "text"),
    ("Division", _division_name, "text"),
    ("Requestor", lambda r: r.requestor.name if r.requestor else None, "text"),
    ("Request Date", lambda r: _day(r.request_date), "date"),
    ("Total Cost", lambda r: r.total_cost, "money"),
    ("Current Level", lambda r: r.current_level, "num"),
    ("Required Levels", lambda r: r.required_levels, "num"),
    ("Budgeted", lambda r: _yn(r.budgeted), "text"),
    ("Replacement", lambda r: _yn(r.replacement), "text"),
    ("Health & Safety", lambda r: _yn(r.health_safety), "text"),
    ("Revenue Generating", lambda r: _yn(r.revenue_generating), "text"),
    ("Environmental", lambda r: _yn(r.environmental), "text"),
    ("Competitive Bids", lambda r: _yn(r.competitive_bids), "text"),
    ("Lease Recommended", lambda r: _yn(r.lease_recommended), "text"),
    ("Asset Life", lambda r: r.asset_life, "text"),
    ("IRR After Tax", lambda r: r.irr_after_tax, "num"),
    ("First-Year EBIT", lambda r: r.first_year_ebit, "money"),
    ("Annual Savings", lambda r: r.annual_savings, "money"),
    ("Payback Years", lambda r: r.payback_years, "num"),
    ("NPV Savings", lambda r: r.npv_savings, "money"),
    ("Asset Number", lambda r: r.asset_number, "text"),
    ("GL Account", lambda r: r.gl_account, "text"),
    ("Useful Life (Years)", lambda r: r.useful_life_years, "num"),
    ("Useful Life (Months)", lambda r: r.useful_life_months, "num"),
    ("In-Service Date", lambda r: _day(r.in_service_date), "date"),
    ("Cost: Autos & Trucks", lambda r: r.cost_autos_trucks, "money"),
    ("Cost: Machinery & Equipment", lambda r: r.cost_machinery, "money"),
    ("Cost: Improvements", lambda r: r.cost_improvements, "money"),
    ("Cost: Furniture & Fixtures", lambda r: r.cost_furniture, "money"),
    ("Cost: IT / Computer", lambda r: r.cost_it_computer, "money"),
    ("Cost: Miscellaneous", lambda r: r.cost_misc, "money"),
    ("Finance Completed", lambda r: _yn(r.finance_completed), "text"),
]


def build_workbook(rows) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "CAPEX Requests"
    ws.append([header for header, _, _ in COLUMNS])
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    ws.freeze_panes = "A2"
    for req in rows:
        ws.append([getter(req) for _, getter, _ in COLUMNS])
        for idx, (_, _, kind) in enumerate(COLUMNS, start=1):
            if kind == "money":
                ws.cell(row=ws.max_row, column=idx).number_format = _MONEY_FMT
            elif kind == "date":
                ws.cell(row=ws.max_row, column=idx).number_format = _DATE_FMT
    for idx in range(1, len(COLUMNS) + 1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = 18
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_xlsx(viewer, scope="mine", status=None, division_id=None, q=None) -> bytes:
    rows = request_service.list_requests(
        viewer, scope=scope, status=status, division_id=division_id)
    rows = [r for r in rows if matches_query(r, q)]
    rows.sort(key=lambda r: r.number or "")
    return build_workbook(rows)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_export_service.py -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/services/export_service.py backend/tests/test_export_service.py
git commit -m "export: xlsx workbook builder + list-search filter (openpyxl)"
```

---

### Task 2: Export API route

**Files:**
- Modify: `backend/app/blueprints/requests.py` (add route after `list_requests_route`)
- Test: `backend/tests/test_export_api.py`

**Interfaces:**
- Consumes: `export_service.export_xlsx(viewer, scope, status, division_id, q)` (Task 1).
- Produces: `GET /api/requests/export.xlsx?scope=&status=&division_id=&q=` → xlsx download. (Werkzeug ranks the static segment `export.xlsx` above the `/<request_id>` converter, so no route conflict.)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_export_api.py`:

```python
from io import BytesIO

from openpyxl import load_workbook

from tests.factories import make_user, make_division, make_draft


def _login(client, user):
    client.post("/api/auth/login",
                json={"email": user.email, "password": "secret123"})


def _sheet(res):
    assert res.status_code == 200
    assert res.mimetype == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return load_workbook(BytesIO(res.data)).active


def _numbers(ws):
    return [row[0].value for row in ws.iter_rows(min_row=2)]


def test_export_requires_login(client, app):
    assert client.get("/api/requests/export.xlsx").status_code == 401


def test_export_mine_only_own_rows(client, app):
    a = make_user("a", roles='["REQUESTOR"]')
    b = make_user("b", roles='["REQUESTOR"]')
    div = make_division()
    make_draft(a.id, div.id, number="CX000001")
    make_draft(b.id, div.id, number="CX000002")
    _login(client, a)
    ws = _sheet(client.get("/api/requests/export.xlsx?scope=mine"))
    assert _numbers(ws) == ["CX000001"]


def test_export_scope_all_denied_for_plain_requestor(client, app):
    a = make_user("a", roles='["REQUESTOR"]')
    b = make_user("b", roles='["REQUESTOR"]')
    div = make_division()
    make_draft(a.id, div.id, number="CX000001")
    make_draft(b.id, div.id, number="CX000002")
    _login(client, a)
    # Same fallback as the list route: non-ADMIN/FINANCE gets own rows.
    ws = _sheet(client.get("/api/requests/export.xlsx?scope=all"))
    assert _numbers(ws) == ["CX000001"]


def test_export_scope_all_for_finance_with_filters(client, app):
    fin = make_user("fin", roles='["FINANCE"]')
    a = make_user("a", roles='["REQUESTOR"]')
    b = make_user("b", roles='["REQUESTOR"]')
    div = make_division()
    make_draft(a.id, div.id, number="CX000001")
    make_draft(b.id, div.id, number="CX000002")
    _login(client, fin)
    ws = _sheet(client.get("/api/requests/export.xlsx?scope=all"))
    assert _numbers(ws) == ["CX000001", "CX000002"]
    ws = _sheet(client.get("/api/requests/export.xlsx?scope=all&q=CX000002"))
    assert _numbers(ws) == ["CX000002"]
    ws = _sheet(client.get(
        "/api/requests/export.xlsx?scope=all&status=APPROVED"))
    assert _numbers(ws) == []


def test_export_sets_attachment_filename(client, app):
    a = make_user("a", roles='["REQUESTOR"]')
    _login(client, a)
    res = client.get("/api/requests/export.xlsx")
    disp = res.headers["Content-Disposition"]
    assert disp.startswith("attachment; filename=capex-requests-")
    assert disp.endswith(".xlsx")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_export_api.py -q`
Expected: FAIL — the 200-status asserts get 404 (route doesn't exist); the login test may already pass (401 fires before routing? No — Flask 404s unauthenticated on unknown routes only after routing, so expect 404 there too).

- [ ] **Step 3: Add the route**

In `backend/app/blueprints/requests.py`:

1. Extend the service import line:

```python
from app.services import request_service, workflow_service, notify, attachment_service, export_service
```

2. Add `from datetime import date` below the existing imports at the top of the file.

3. Insert this route directly after `list_requests_route` (before `create_request`):

```python
@bp.get("/export.xlsx")
@login_required
def export_requests_route():
    data = export_service.export_xlsx(
        current_user,
        scope=request.args.get("scope", "mine"),
        status=request.args.get("status") or None,
        division_id=request.args.get("division_id") or None,
        q=request.args.get("q") or None,
    )
    filename = f"capex-requests-{date.today().isoformat()}.xlsx"
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_export_api.py tests/test_export_service.py -q`
Expected: all PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && pytest -q`
Expected: all PASS (no regressions — especially `test_requests_api.py`, confirming `/export.xlsx` doesn't shadow `/<request_id>`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/blueprints/requests.py backend/tests/test_export_api.py
git commit -m "export: GET /api/requests/export.xlsx download route"
```

---

### Task 3: Report service (year summary aggregation)

**Files:**
- Create: `backend/app/services/report_service.py`
- Test: `backend/tests/test_report_service.py`

**Interfaces:**
- Consumes: `CapexRequest` (+ `.actions`, `.division`), `money_str`.
- Produces: `report_service.summary(year=None) -> dict` exactly matching the spec's response shape (`year`, `years`, `totals`, `by_division`, `by_month` (12 rows), `by_status` (6 rows, workflow order), `cycle_time`).
- Definition pinned here: **cycle time is computed over the selected year's (`request_date`) requests whose status is APPROVED** — first `SUBMITTED` action → last `APPROVED` action — keeping every number on the page consistent with the same year bucket. (Task 8 amends the spec's wording to match.)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_report_service.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_report_service.py -q`
Expected: FAIL with `ImportError`/`ModuleNotFoundError` for `report_service`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/services/report_service.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_report_service.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/report_service.py backend/tests/test_report_service.py
git commit -m "reports: year summary aggregation service (Python-side)"
```

---

### Task 4: Reports blueprint (FINANCE/ADMIN only)

**Files:**
- Create: `backend/app/blueprints/reports.py`
- Modify: `backend/app/__init__.py` (register blueprint, after `email_templates_bp`)
- Test: `backend/tests/test_reports_api.py`

**Interfaces:**
- Consumes: `report_service.summary(year)` (Task 3), `app.authz.require_roles`.
- Produces: `GET /api/reports/summary?year=<int>` → JSON summary; 401 anonymous, 403 without FINANCE/ADMIN.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_reports_api.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_reports_api.py -q`
Expected: FAIL — 404s where 401/403/200 expected.

- [ ] **Step 3: Write the blueprint and register it**

Create `backend/app/blueprints/reports.py`:

```python
from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.services import report_service

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/summary")
@require_roles("FINANCE", "ADMIN")
def summary_route():
    return jsonify(report_service.summary(request.args.get("year", type=int)))
```

In `backend/app/__init__.py`, after the `email_templates_bp` registration add:

```python
    from .blueprints.reports import bp as reports_bp
    app.register_blueprint(reports_bp)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_reports_api.py -q`
Expected: all PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && pytest -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/blueprints/reports.py backend/app/__init__.py backend/tests/test_reports_api.py
git commit -m "reports: /api/reports/summary endpoint (FINANCE/ADMIN)"
```

---

### Task 5: Frontend API layer (export helpers + reports client)

**Files:**
- Modify: `frontend/src/api/requests.ts` (append at end)
- Create: `frontend/src/api/reports.ts`
- Test: `frontend/src/api/requests.test.ts` (new)

**Interfaces:**
- Consumes: `ApiError` from `./client` (existing export), `api` from `./client`.
- Produces:
  - `exportRequestsPath(params: { scope?: string; status?: string; q?: string }): string`
  - `downloadRequestsExport(params): Promise<void>` (fetch → blob → anchor click)
  - `getReportSummary(year?: number): Promise<ReportSummary>` and the `ReportSummary` types below.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/api/requests.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { exportRequestsPath } from './requests'

describe('exportRequestsPath', () => {
  it('returns the bare path with no params', () => {
    expect(exportRequestsPath()).toBe('/api/requests/export.xlsx')
    expect(exportRequestsPath({ scope: '', status: '', q: '' })).toBe(
      '/api/requests/export.xlsx')
  })

  it('includes scope, status and trimmed q', () => {
    expect(exportRequestsPath({ scope: 'all', status: 'APPROVED', q: ' CX01 ' }))
      .toBe('/api/requests/export.xlsx?scope=all&status=APPROVED&q=CX01')
  })

  it('drops blank q and encodes special characters', () => {
    expect(exportRequestsPath({ scope: 'mine', q: '   ' })).toBe(
      '/api/requests/export.xlsx?scope=mine')
    expect(exportRequestsPath({ q: 'a&b' })).toBe(
      '/api/requests/export.xlsx?q=a%26b')
  })
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && node ./node_modules/vitest/vitest.mjs run src/api/requests.test.ts`
Expected: FAIL — `exportRequestsPath` is not exported.

- [ ] **Step 3: Implement the helpers**

Append to `frontend/src/api/requests.ts` (and extend the first import line to `import { api, apiUpload, ApiError } from './client'`):

```ts
export interface ExportParams {
  scope?: string
  status?: string
  q?: string
}

export function exportRequestsPath(params: ExportParams = {}): string {
  const qp = new URLSearchParams()
  if (params.scope) qp.set('scope', params.scope)
  if (params.status) qp.set('status', params.status)
  if (params.q?.trim()) qp.set('q', params.q.trim())
  const qs = qp.toString()
  return `/api/requests/export.xlsx${qs ? `?${qs}` : ''}`
}

export async function downloadRequestsExport(params: ExportParams = {}): Promise<void> {
  const res = await fetch(exportRequestsPath(params), { credentials: 'include' })
  if (!res.ok) throw new ApiError(res.status, 'Export failed.')
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const name = /filename=([^;]+)/.exec(disposition)?.[1]?.trim() ?? 'capex-requests.xlsx'
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
```

Create `frontend/src/api/reports.ts`:

```ts
import { api } from './client'

export interface ReportBucket {
  approved_total: string | null
  approved_count: number
  pending_total: string | null
  pending_count: number
}
export interface DivisionBucket extends ReportBucket {
  division: string
}
export interface MonthBucket extends ReportBucket {
  month: number
}
export interface StatusBucket {
  status: string
  count: number
  total: string | null
}
export interface ReportSummary {
  year: number
  years: number[]
  totals: ReportBucket & { request_count: number }
  by_division: DivisionBucket[]
  by_month: MonthBucket[]
  by_status: StatusBucket[]
  cycle_time: { avg_days: number | null; count: number }
}

export function getReportSummary(year?: number): Promise<ReportSummary> {
  return api<ReportSummary>(`/reports/summary${year ? `?year=${year}` : ''}`)
}
```

- [ ] **Step 4: Run test + typecheck to verify they pass**

Run: `cd frontend && node ./node_modules/vitest/vitest.mjs run src/api/requests.test.ts && node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
Expected: test PASS, tsc clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/requests.ts frontend/src/api/requests.test.ts frontend/src/api/reports.ts
git commit -m "frontend api: export download helpers + reports client"
```

---

### Task 6: Requests list — "All" scope tab + Export button

**Files:**
- Modify: `frontend/src/routes/RequestsListPage.tsx` (component top half only; `COLUMNS` and `RequestsTable` below it stay untouched)
- Test: `frontend/src/routes/RequestsListPage.test.tsx` (new)

**Interfaces:**
- Consumes: `useMe()` (`data.roles: string[]`), `downloadRequestsExport(params)` (Task 5), `DownloadIcon` from `../components/ActionIcons`, `Button` from `../components/ui/Button`.
- Produces: UI only. Export always sends `{ scope, status, q }` matching current controls.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/routes/RequestsListPage.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RequestsListPage from './RequestsListPage'
import * as reqApi from '../api/requests'
import { useMe } from '../auth/useMe'

vi.mock('../api/requests', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/requests')>()
  return { ...mod, listRequests: vi.fn(), downloadRequestsExport: vi.fn() }
})
vi.mock('../auth/useMe')

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <RequestsListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function mockMe(roles: string[]) {
  vi.mocked(useMe).mockReturnValue({
    data: { id: 'u1', name: 'U', email: 'u@x.com', roles,
            division_id: null, must_change_password: false },
  } as ReturnType<typeof useMe>)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(reqApi.listRequests).mockResolvedValue([])
})

describe('RequestsListPage', () => {
  it('hides the All tab for a plain requestor', async () => {
    mockMe(['REQUESTOR'])
    renderPage()
    await waitFor(() => expect(reqApi.listRequests).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: 'All' })).not.toBeInTheDocument()
  })

  it('shows the All tab for FINANCE and lists with scope=all', async () => {
    mockMe(['FINANCE'])
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'All' }))
    await waitFor(() => expect(reqApi.listRequests).toHaveBeenLastCalledWith(
      { scope: 'all', status: undefined }))
  })

  it('exports with the current scope, status and search text', async () => {
    mockMe(['FINANCE'])
    vi.mocked(reqApi.downloadRequestsExport).mockResolvedValue()
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'All' }))
    fireEvent.change(screen.getByLabelText('Search requests'),
      { target: { value: 'CX0001' } })
    fireEvent.click(screen.getByRole('button', { name: /Export/i }))
    await waitFor(() => expect(reqApi.downloadRequestsExport)
      .toHaveBeenCalledWith({ scope: 'all', status: '', q: 'CX0001' }))
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node ./node_modules/vitest/vitest.mjs run src/routes/RequestsListPage.test.tsx`
Expected: FAIL — no `All` tab / no Export button (also the first test currently passes; that's fine, the suite as a whole fails).

- [ ] **Step 3: Update the component**

In `frontend/src/routes/RequestsListPage.tsx`, replace the imports and the `RequestsListPage` function with the code below (keep `COLUMNS` and `RequestsTable` exactly as they are):

```tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { listRequests, downloadRequestsExport, type RequestSummary } from '../api/requests'
import { useMe } from '../auth/useMe'
import { Select } from '../components/ui/Select'
import { Button } from '../components/ui/Button'
import { BrandCard } from '../components/ui/BrandCard'
import { StatusBadge } from '../components/ui/Badge'
import { SearchIcon, FilterIcon, ViewIcon, DownloadIcon } from '../components/ActionIcons'
import { sortRequests, filterRequests, type SortDir, type SortKey } from './requestsSort'

const STATUSES = ['', 'DRAFT', 'PENDING_L1', 'PENDING_L2', 'PENDING_L3', 'APPROVED', 'REJECTED']

const SCOPE_LABELS: Record<string, string> = {
  mine: 'My Requests',
  assigned: 'Assigned to me',
  all: 'All',
}

export default function RequestsListPage() {
  const { data: me } = useMe()
  const [scope, setScope] = useState('mine')
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const canSeeAll = (me?.roles ?? []).some((r) => r === 'ADMIN' || r === 'FINANCE')
  const scopes = canSeeAll ? ['mine', 'assigned', 'all'] : ['mine', 'assigned']
  const { data: rows = [] } = useQuery({
    queryKey: ['requests', scope, status],
    queryFn: () => listRequests({ scope, status: status || undefined }),
  })

  async function handleExport() {
    setExporting(true)
    setExportError('')
    try {
      await downloadRequestsExport({ scope, status, q: query })
    } catch {
      setExportError('Export failed.')
    } finally {
      setExporting(false)
    }
  }

  const filters = (
    <div className="flex flex-wrap items-center gap-3 border-b border-border bg-surface-2 px-7 py-3">
      <div className="inline-flex rounded-md border border-border bg-surface p-0.5">
        {scopes.map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`rounded px-3 py-1 text-sm font-medium transition ${
              scope === s ? 'bg-accent text-accent-fg' : 'text-muted hover:text-fg'
            }`}
          >
            {SCOPE_LABELS[s]}
          </button>
        ))}
      </div>
      <div className="relative">
        <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted">
          <SearchIcon size={16} />
        </span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search requests…"
          aria-label="Search requests"
          className="w-56 rounded-md border border-border bg-surface py-1.5 pl-8 pr-3 text-sm text-fg outline-none focus:border-accent"
        />
      </div>
      <div className="flex items-center gap-1.5 text-muted">
        <FilterIcon size={16} />
        <div className="w-48">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s === '' ? 'All statuses' : s}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className="ml-auto flex items-center gap-2">
        {exportError && <span className="text-sm text-red-600">{exportError}</span>}
        <Button variant="secondary" onClick={handleExport} disabled={exporting}>
          <DownloadIcon size={15} />
          {exporting ? 'Exporting…' : 'Export'}
        </Button>
      </div>
    </div>
  )

  return (
    <BrandCard title="Requests" subtitle="Capital expenditure requests" mark="requests" subheader={filters}>
      <RequestsTable rows={filterRequests(rows, query)} />
    </BrandCard>
  )
}
```

- [ ] **Step 4: Run the tests + typecheck to verify they pass**

Run: `cd frontend && node ./node_modules/vitest/vitest.mjs run src/routes/RequestsListPage.test.tsx && node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
Expected: PASS, tsc clean. (`Button` extends `ButtonHTMLAttributes` and spreads props, so `disabled` works as written — verified.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/RequestsListPage.tsx frontend/src/routes/RequestsListPage.test.tsx
git commit -m "requests list: All scope tab (ADMIN/FINANCE) + Export to Excel button"
```

---

### Task 7: Reports page + navigation wiring

**Files:**
- Modify: `frontend/src/components/NavIcons.tsx` (add `ReportsIcon`)
- Modify: `frontend/src/components/ui/BrandCard.tsx` (add `reports` mark)
- Modify: `frontend/src/components/AppShell.tsx` (nav item)
- Modify: `frontend/src/App.tsx` (route)
- Create: `frontend/src/routes/ReportsPage.tsx`
- Test: `frontend/src/routes/ReportsPage.test.tsx` (new)

**Interfaces:**
- Consumes: `getReportSummary` + `ReportSummary` types (Task 5), `useMe()`, `BrandCard`, `StatCard`, `Select`.
- Produces: route `/reports`; nav entry visible to FINANCE/ADMIN; page redirects others to `/`.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/routes/ReportsPage.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ReportsPage from './ReportsPage'
import * as reportsApi from '../api/reports'
import { useMe } from '../auth/useMe'
import type { ReportSummary } from '../api/reports'

vi.mock('../api/reports')
vi.mock('../auth/useMe')

const SUMMARY: ReportSummary = {
  year: 2026,
  years: [2026, 2025],
  totals: { approved_total: '30000', approved_count: 2,
            pending_total: '5000', pending_count: 1, request_count: 4 },
  by_division: [{ division: '100 — Field Services', approved_total: '30000',
                  approved_count: 2, pending_total: '5000', pending_count: 1 }],
  by_month: Array.from({ length: 12 }, (_, i) => ({
    month: i + 1, approved_total: i === 2 ? '30000' : '0',
    approved_count: i === 2 ? 2 : 0, pending_total: '0', pending_count: 0 })),
  by_status: [
    { status: 'DRAFT', count: 1, total: '100' },
    { status: 'PENDING_L1', count: 1, total: '5000' },
    { status: 'PENDING_L2', count: 0, total: '0' },
    { status: 'PENDING_L3', count: 0, total: '0' },
    { status: 'APPROVED', count: 2, total: '30000' },
    { status: 'REJECTED', count: 0, total: '0' },
  ],
  cycle_time: { avg_days: 3.5, count: 2 },
}

function mockMe(roles: string[]) {
  vi.mocked(useMe).mockReturnValue({
    data: { id: 'u1', name: 'U', email: 'u@x.com', roles,
            division_id: null, must_change_password: false },
  } as ReturnType<typeof useMe>)
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/reports']}>
        <Routes>
          <Route path="/" element={<div>Dashboard Home</div>} />
          <Route path="/reports" element={<ReportsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(reportsApi.getReportSummary).mockResolvedValue(SUMMARY)
})

describe('ReportsPage', () => {
  it('redirects non-finance users to the dashboard', async () => {
    mockMe(['REQUESTOR'])
    renderPage()
    expect(await screen.findByText('Dashboard Home')).toBeInTheDocument()
    expect(reportsApi.getReportSummary).not.toHaveBeenCalled()
  })

  it('renders stats and tables for FINANCE', async () => {
    mockMe(['FINANCE'])
    renderPage()
    expect(await screen.findByText('$30,000')).toBeInTheDocument()
    expect(screen.getByText('100 — Field Services')).toBeInTheDocument()
    expect(screen.getByText('3.5')).toBeInTheDocument()
    expect(screen.getByText('Spend by division')).toBeInTheDocument()
    expect(screen.getByText('Spend by month')).toBeInTheDocument()
    expect(screen.getByText('By status')).toBeInTheDocument()
  })

  it('refetches when the year changes', async () => {
    mockMe(['ADMIN'])
    renderPage()
    await screen.findByText('$30,000')
    fireEvent.change(screen.getByLabelText('Year'), { target: { value: '2025' } })
    await waitFor(() =>
      expect(reportsApi.getReportSummary).toHaveBeenLastCalledWith(2025))
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && node ./node_modules/vitest/vitest.mjs run src/routes/ReportsPage.test.tsx`
Expected: FAIL — `./ReportsPage` module not found.

- [ ] **Step 3: Add the icon, mark, page, nav item, and route**

3a. `frontend/src/components/NavIcons.tsx` — append after `ProfileIcon`:

```tsx
export function ReportsIcon(props: NavIconProps) {
  return (
    <Icon {...props}>
      <path d="M4 4v16h16" />
      <path d="M9 16v-5" />
      <path d="M13 16V8" />
      <path d="M17 16v-3" />
    </Icon>
  )
}
```

3b. `frontend/src/components/ui/BrandCard.tsx` — add `ReportsIcon` to the import from `'../NavIcons'`, add `| 'reports'` to the `PageMark` union, and add `reports: ReportsIcon,` to `MARKS`.

3c. Create `frontend/src/routes/ReportsPage.tsx`:

```tsx
import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getReportSummary, type ReportBucket } from '../api/reports'
import { useMe } from '../auth/useMe'
import { BrandCard } from '../components/ui/BrandCard'
import { StatCard } from '../components/ui/Card'
import { Select } from '../components/ui/Select'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function money(v: string | null | undefined): string {
  return `$${Number(v ?? 0).toLocaleString()}`
}

const THEAD =
  'border-b border-border bg-brand-sky/25 text-left text-xs uppercase tracking-wide ' +
  'text-brand-navy dark:bg-brand-sky/10 dark:text-brand-sky'

function Bar({ value, max }: { value: number; max: number }) {
  const pct = max > 0 && value > 0 ? Math.max(2, Math.round((value / max) * 100)) : 0
  return (
    <div className="h-2 w-full min-w-24 rounded bg-surface-2">
      <div className="h-2 rounded bg-accent" style={{ width: `${pct}%` }} />
    </div>
  )
}

function BucketTable({ title, rows }: {
  title: string
  rows: (ReportBucket & { label: string })[]
}) {
  const max = Math.max(...rows.map((r) => Number(r.approved_total ?? 0)), 0)
  return (
    <section className="mt-8 first:mt-0">
      <h2 className="mb-2 text-sm font-semibold text-fg">{title}</h2>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className={`${THEAD} [&>th]:py-2 [&>th]:pr-4 [&>th:first-child]:pl-2`}>
              <th className="font-semibold">{title === 'Spend by month' ? 'Month' : 'Division'}</th>
              <th className="text-right font-semibold">Approved</th>
              <th className="w-1/3 font-semibold"><span className="sr-only">Share</span></th>
              <th className="text-right font-semibold">Pending</th>
              <th className="pr-2 text-right font-semibold">Requests</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className="border-b border-border last:border-0">
                <td className="py-2 pl-2 pr-4 text-fg">{r.label}</td>
                <td className="py-2 pr-4 text-right font-medium text-fg">{money(r.approved_total)}</td>
                <td className="py-2 pr-4"><Bar value={Number(r.approved_total ?? 0)} max={max} /></td>
                <td className="py-2 pr-4 text-right text-muted">{money(r.pending_total)}</td>
                <td className="py-2 pr-2 text-right text-muted">{r.approved_count + r.pending_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default function ReportsPage() {
  const { data: me } = useMe()
  const [year, setYear] = useState<number | undefined>(undefined)
  const canView = (me?.roles ?? []).some((r) => r === 'FINANCE' || r === 'ADMIN')
  const { data } = useQuery({
    queryKey: ['report-summary', year],
    queryFn: () => getReportSummary(year),
    enabled: !!me && canView,
  })

  if (me && !canView) return <Navigate to="/" replace />

  const yearOptions = data?.years ?? (year ? [year] : [])
  const statusMax = Math.max(...(data?.by_status ?? []).map((s) => Number(s.total ?? 0)), 0)

  const subheader = (
    <div className="flex items-center gap-3 border-b border-border bg-surface-2 px-7 py-3">
      <label htmlFor="report-year" className="text-sm font-medium text-muted">Year</label>
      <div className="w-32">
        <Select
          id="report-year"
          aria-label="Year"
          value={String(data?.year ?? year ?? '')}
          onChange={(e) => setYear(Number(e.target.value))}
        >
          {yearOptions.map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </Select>
      </div>
    </div>
  )

  return (
    <BrandCard
      title="Reports"
      subtitle="Spend and cycle-time summaries"
      mark="reports"
      subheader={subheader}
    >
      {!data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard label="Approved Spend" value={money(data.totals.approved_total)} accent
              sub={`${data.totals.approved_count} requests`} />
            <StatCard label="Pending Pipeline" value={money(data.totals.pending_total)}
              sub={`${data.totals.pending_count} requests`} />
            <StatCard label="Requests" value={data.totals.request_count}
              sub={`in ${data.year}`} />
            <StatCard label="Avg Days to Approve"
              value={data.cycle_time.avg_days ?? '—'}
              sub={`${data.cycle_time.count} approved`} />
          </div>

          <div className="mt-8">
            <BucketTable
              title="Spend by division"
              rows={data.by_division.map((d) => ({ ...d, label: d.division }))}
            />
            <BucketTable
              title="Spend by month"
              rows={data.by_month.map((m) => ({ ...m, label: MONTHS[m.month - 1] }))}
            />
            <section className="mt-8">
              <h2 className="mb-2 text-sm font-semibold text-fg">By status</h2>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className={`${THEAD} [&>th]:py-2 [&>th]:pr-4 [&>th:first-child]:pl-2`}>
                      <th className="font-semibold">Status</th>
                      <th className="text-right font-semibold">Requests</th>
                      <th className="text-right font-semibold">Total</th>
                      <th className="w-1/3 pr-2 font-semibold"><span className="sr-only">Share</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_status.map((s) => (
                      <tr key={s.status} className="border-b border-border last:border-0">
                        <td className="py-2 pl-2 pr-4 text-fg">{s.status}</td>
                        <td className="py-2 pr-4 text-right text-fg">{s.count}</td>
                        <td className="py-2 pr-4 text-right font-medium text-fg">{money(s.total)}</td>
                        <td className="py-2 pr-2"><Bar value={Number(s.total ?? 0)} max={statusMax} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </>
      )}
    </BrandCard>
  )
}
```

Note: `Select` extends `SelectHTMLAttributes` and spreads props, so `id`/`aria-label` work as written — verified.

3d. `frontend/src/components/AppShell.tsx` — add `ReportsIcon` to the `./NavIcons` import list and add to the `Overview` section items, after the `My Requests` entry:

```tsx
      { to: '/reports', label: 'Reports', icon: ReportsIcon, roles: ['FINANCE', 'ADMIN'] },
```

3e. `frontend/src/App.tsx` — add `import ReportsPage from './routes/ReportsPage'` and, inside the `ProtectedLayout` route group after the `/requests/:id` route:

```tsx
        <Route path="/reports" element={<ReportsPage />} />
```

- [ ] **Step 4: Run tests + typecheck to verify they pass**

Run: `cd frontend && node ./node_modules/vitest/vitest.mjs run src/routes/ReportsPage.test.tsx && node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
Expected: PASS, tsc clean.

- [ ] **Step 5: Run the whole frontend suite + build**

Run: `cd frontend && node ./node_modules/vitest/vitest.mjs run && node ./node_modules/vite/bin/vite.js build`
Expected: all tests PASS, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/NavIcons.tsx frontend/src/components/ui/BrandCard.tsx frontend/src/components/AppShell.tsx frontend/src/App.tsx frontend/src/routes/ReportsPage.tsx frontend/src/routes/ReportsPage.test.tsx
git commit -m "reports: FINANCE/ADMIN Reports page with year picker, spend tables, cycle time"
```

---

### Task 8: Docs, spec amendment, full verification

**Files:**
- Modify: `CLAUDE.md`
- Modify: `PHASE2-PROPOSALS.md`
- Modify: `docs/superpowers/specs/2026-07-17-exports-reporting-design.md`

- [ ] **Step 1: Update CLAUDE.md**

- Blueprints list: add `reports` (`/api/reports`, FINANCE/ADMIN summary endpoint) to the `blueprints/` bullet.
- Services list: add `export_service` (xlsx export of the requests list via openpyxl) and `report_service` (year summary aggregates, Python-side) to the `services/` bullet.
- Frontend `routes/` bullet: add `ReportsPage` (FINANCE/ADMIN `/reports`: year picker, spend by division/month/status tables with CSS bars, cycle time).
- `RequestsListPage` mention: note the Export-to-Excel button and the ADMIN/FINANCE "All" scope tab.
- BrandCard mark list: add `reports` to the `mark` page-key enumeration.
- Testing section: update the backend test count if stated (run `cd backend && pytest -q` and use the reported number).

- [ ] **Step 2: Update PHASE2-PROPOSALS.md**

In item 2 (Exports & reporting), prefix the description with `**BUILT 2026-07-17**` and a pointer to `docs/superpowers/specs/2026-07-17-exports-reporting-design.md`.

- [ ] **Step 3: Amend the spec's cycle-time wording**

In `docs/superpowers/specs/2026-07-17-exports-reporting-design.md`, replace the `cycle_time` bullet with:

```markdown
- `cycle_time`: over the selected year's (`request_date`) requests whose
  status is APPROVED — days from the first SUBMITTED `ApprovalAction` to the
  last APPROVED action; never-approved requests excluded; `avg_days` null
  when count is 0. (Keeps every number on the page consistent with the same
  request_date-year bucket.)
```

- [ ] **Step 4: Full verification**

Run: `cd backend && pytest -q`
Expected: all PASS.
Run: `cd frontend && node ./node_modules/vitest/vitest.mjs run && node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json && node ./node_modules/vite/bin/vite.js build`
Expected: all PASS / clean / build succeeds.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md PHASE2-PROPOSALS.md docs/superpowers/specs/2026-07-17-exports-reporting-design.md
git commit -m "docs: record exports & reporting feature (CLAUDE.md, phase-2 status, spec cycle-time wording)"
```
