# M4 — Admin & Profile Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** REST APIs for the admin domains (users, divisions, approval thresholds) and self-service profile (change password, set delegate), with role-based authorization and Pydantic validation — bringing the backend to Phase-1 parity.

**Architecture:** A `require_roles` decorator (built on Flask-Login) guards admin routes; a `ServiceError` exception + error handler turns service-layer failures into JSON responses; Pydantic models validate request bodies (ValidationError → 400). Each domain follows blueprint → service → model. Output is serialized by small per-domain functions (roles come from `User.roles_list`, money as strings). The React admin UI (M5) consumes these.

**Tech Stack:** Flask, Flask-Login, Pydantic v2 (+ email-validator), SQLAlchemy, pytest. Builds on M1–M3.

## Global Constraints

- Inherits all prior constraints. **API JSON is snake_case** (e.g. `division_id`, `max_amount`) to keep serialization simple.
- **Authorization:** admin endpoints require the `ADMIN` role → `401` if unauthenticated, `403` if authenticated without the role. Profile endpoints require any authenticated user (self).
- **Money** (`max_amount`) serialized as a string or `null` to preserve precision.
- **Roles** validated against `ROLES = ["REQUESTOR", "APPROVER", "FINANCE", "ADMIN"]`; stored as a JSON string.
- Passwords: minimum 8 characters. Username/email lowercased + unique (case-insensitive).

---

### Task 1: Authorization, roles helper, ServiceError handling

**Files:**
- Create: `backend/app/roles.py`
- Create: `backend/app/authz.py`
- Create: `backend/app/services/errors.py`
- Modify: `backend/app/__init__.py` (register error handlers)
- Modify: `backend/requirements.txt` (add `email-validator`)
- Test: `backend/tests/test_authz.py`

**Interfaces:**
- Consumes: Flask-Login `current_user`, `login_required`.
- Produces:
  - `app.roles.ROLES` (list), `serialize_roles(roles) -> str`, `valid_roles(roles) -> bool`.
  - `app.authz.require_roles(*roles)` decorator → 401 unauthenticated, 403 missing role.
  - `app.services.errors.ServiceError(message: str, status: int = 400)`.
  - `create_app` registers handlers: `ServiceError` → `{error}` at its status; Pydantic `ValidationError` → `{error, details}` at 400.

- [ ] **Step 1: Add email-validator dependency**

Append to `backend/requirements.txt`:
```
email-validator>=2.0
```
Install: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_authz.py`:
```python
import pytest

from app.extensions import db
from app.models import User
from app.services.security import hash_password
from app.authz import require_roles
from app.services.errors import ServiceError


@pytest.fixture
def app_with_routes(app):
    @app.get("/api/_admin_only")
    @require_roles("ADMIN")
    def _admin_only():
        return {"ok": True}

    @app.get("/api/_boom")
    def _boom():
        raise ServiceError("nope", 409)

    return app


def _make_user(roles):
    u = User(username="u", email="u@x.com", name="U",
             password_hash=hash_password("secret123"), roles=roles)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client):
    return client.post("/api/auth/login", json={"username": "u", "password": "secret123"})


def test_admin_route_401_when_anonymous(app_with_routes):
    client = app_with_routes.test_client()
    assert client.get("/api/_admin_only").status_code == 401


def test_admin_route_403_when_missing_role(app_with_routes):
    client = app_with_routes.test_client()
    _make_user('["REQUESTOR"]')
    _login(client)
    assert client.get("/api/_admin_only").status_code == 403


def test_admin_route_200_when_admin(app_with_routes):
    client = app_with_routes.test_client()
    _make_user('["ADMIN"]')
    _login(client)
    r = client.get("/api/_admin_only")
    assert r.status_code == 200 and r.get_json() == {"ok": True}


def test_service_error_becomes_json(app_with_routes):
    client = app_with_routes.test_client()
    r = client.get("/api/_boom")
    assert r.status_code == 409
    assert r.get_json()["error"] == "nope"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_authz.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.authz'`.

- [ ] **Step 4: Write the roles helper**

`backend/app/roles.py`:
```python
import json

ROLES = ["REQUESTOR", "APPROVER", "FINANCE", "ADMIN"]


def valid_roles(roles) -> bool:
    return all(r in ROLES for r in roles)


def serialize_roles(roles) -> str:
    # Keep only known roles, in canonical order.
    return json.dumps([r for r in ROLES if r in roles])
```

- [ ] **Step 5: Write the ServiceError**

`backend/app/services/errors.py`:
```python
class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status
```

- [ ] **Step 6: Write the require_roles decorator**

`backend/app/authz.py`:
```python
from functools import wraps

from flask import jsonify
from flask_login import login_required, current_user


def require_roles(*roles):
    def decorator(fn):
        @login_required
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not any(r in current_user.roles_list for r in roles):
                return jsonify(error="Forbidden."), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
```

- [ ] **Step 7: Register error handlers in the app factory**

`backend/app/__init__.py` — add imports at top:
```python
from pydantic import ValidationError

from .services.errors import ServiceError
```
And inside `create_app`, after the blueprints are registered (before `return app`):
```python
    @app.errorhandler(ServiceError)
    def _handle_service_error(err: ServiceError):
        return jsonify(error=err.message), err.status

    @app.errorhandler(ValidationError)
    def _handle_validation_error(err: ValidationError):
        return jsonify(error="Validation failed.", details=err.errors()), 400
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_authz.py -v`
Expected: all 4 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/roles.py backend/app/authz.py backend/app/services/errors.py backend/app/__init__.py backend/requirements.txt backend/tests/test_authz.py
git commit -m "feat(backend): role-based authorization, ServiceError + validation handlers"
```

---

### Task 2: Users API

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/services/user_service.py`
- Create: `backend/app/blueprints/users.py`
- Modify: `backend/app/__init__.py` (register blueprint)
- Test: `backend/tests/test_users_api.py`

**Interfaces:**
- Consumes: `require_roles`, `ServiceError`, roles helper, `security.hash_password`.
- Produces:
  - Service: `list_users()`, `create_user(*, username, email, name, password, roles, division_id)`, `update_user(user_id, *, name, email, roles, division_id, active)`, `admin_reset_password(user_id, password)`.
  - Endpoints (ADMIN): `GET/POST /api/users`, `PATCH /api/users/<id>`, `POST /api/users/<id>/reset-password`.
  - User JSON: `{id, username, email, name, roles: [], active, division_id}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_users_api.py`:
```python
from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _admin(client):
    db.session.add(User(username="admin", email="a@x.com", name="Admin",
                        password_hash=hash_password("secret123"), roles='["ADMIN"]'))
    db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})


def test_list_requires_admin(client):
    assert client.get("/api/users").status_code == 401


def test_admin_can_create_and_list_users(client, app):
    _admin(client)
    r = client.post("/api/users", json={
        "username": "JDoe", "email": "JDoe@x.com", "name": "J Doe",
        "password": "password1", "roles": ["REQUESTOR"], "division_id": None,
    })
    assert r.status_code == 201
    body = r.get_json()
    assert body["username"] == "jdoe" and body["email"] == "jdoe@x.com"
    assert body["roles"] == ["REQUESTOR"]
    listing = client.get("/api/users").get_json()
    assert any(u["username"] == "jdoe" for u in listing)


def test_duplicate_username_conflicts(client, app):
    _admin(client)
    payload = {"username": "dup", "email": "dup@x.com", "name": "D",
               "password": "password1", "roles": ["REQUESTOR"]}
    assert client.post("/api/users", json=payload).status_code == 201
    assert client.post("/api/users", json={**payload, "email": "other@x.com"}).status_code == 409


def test_short_password_is_validation_error(client, app):
    _admin(client)
    r = client.post("/api/users", json={
        "username": "x", "email": "x@x.com", "name": "X", "password": "short", "roles": ["REQUESTOR"]})
    assert r.status_code == 400


def test_update_user(client, app):
    _admin(client)
    created = client.post("/api/users", json={
        "username": "e", "email": "e@x.com", "name": "E",
        "password": "password1", "roles": ["REQUESTOR"]}).get_json()
    r = client.patch(f"/api/users/{created['id']}", json={
        "name": "Edited", "email": "e@x.com", "roles": ["REQUESTOR", "APPROVER"],
        "division_id": None, "active": False})
    assert r.status_code == 200
    body = r.get_json()
    assert body["name"] == "Edited" and body["active"] is False
    assert set(body["roles"]) == {"REQUESTOR", "APPROVER"}


def test_admin_reset_password(client, app):
    _admin(client)
    created = client.post("/api/users", json={
        "username": "r", "email": "r@x.com", "name": "R",
        "password": "password1", "roles": ["REQUESTOR"]}).get_json()
    assert client.post(f"/api/users/{created['id']}/reset-password",
                       json={"password": "newpassword1"}).status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_users_api.py -v`
Expected: FAIL — 404s / import errors (blueprint absent).

- [ ] **Step 3: Write the Pydantic schemas**

`backend/app/schemas/__init__.py`:
```python
```
(empty package marker)

`backend/app/schemas/user.py`:
```python
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    email: EmailStr
    name: str = Field(min_length=1)
    password: str = Field(min_length=8)
    roles: list[str] = Field(default_factory=lambda: ["REQUESTOR"])
    division_id: str | None = None


class UserUpdate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    roles: list[str]
    division_id: str | None = None
    active: bool = True


class PasswordIn(BaseModel):
    password: str = Field(min_length=8)
```

- [ ] **Step 4: Write the user service**

`backend/app/services/user_service.py`:
```python
from app.extensions import db
from app.models import User
from app.roles import serialize_roles, valid_roles
from app.services.errors import ServiceError
from app.services.security import hash_password


def list_users():
    return db.session.query(User).order_by(User.username).all()


def create_user(*, username, email, name, password, roles, division_id):
    if not valid_roles(roles):
        raise ServiceError("Invalid role.")
    uname = username.strip().lower()
    mail = email.strip().lower()
    clash = db.session.query(User).filter(
        (User.username == uname) | (User.email == mail)
    ).first()
    if clash is not None:
        raise ServiceError("Username or email already exists.", 409)
    user = User(
        username=uname, email=mail, name=name.strip(),
        password_hash=hash_password(password),
        roles=serialize_roles(roles), division_id=division_id or None,
    )
    db.session.add(user)
    db.session.commit()
    return user


def update_user(user_id, *, name, email, roles, division_id, active):
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", 404)
    if not valid_roles(roles):
        raise ServiceError("Invalid role.")
    mail = email.strip().lower()
    clash = db.session.query(User).filter(User.email == mail, User.id != user_id).first()
    if clash is not None:
        raise ServiceError("Email already in use.", 409)
    user.name = name.strip()
    user.email = mail
    user.roles = serialize_roles(roles)
    user.division_id = division_id or None
    user.active = active
    db.session.commit()
    return user


def admin_reset_password(user_id, password):
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", 404)
    user.password_hash = hash_password(password)
    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()
    return user
```

- [ ] **Step 5: Write the blueprint**

`backend/app/blueprints/users.py`:
```python
from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.user import UserCreate, UserUpdate, PasswordIn
from app.services import user_service

bp = Blueprint("users", __name__, url_prefix="/api/users")


def user_out(u):
    return {
        "id": u.id, "username": u.username, "email": u.email, "name": u.name,
        "roles": u.roles_list, "active": u.active, "division_id": u.division_id,
    }


@bp.get("")
@require_roles("ADMIN")
def list_users():
    return jsonify([user_out(u) for u in user_service.list_users()])


@bp.post("")
@require_roles("ADMIN")
def create_user():
    data = UserCreate(**(request.get_json(silent=True) or {}))
    user = user_service.create_user(**data.model_dump())
    return jsonify(user_out(user)), 201


@bp.patch("/<user_id>")
@require_roles("ADMIN")
def update_user(user_id):
    data = UserUpdate(**(request.get_json(silent=True) or {}))
    user = user_service.update_user(user_id, **data.model_dump())
    return jsonify(user_out(user))


@bp.post("/<user_id>/reset-password")
@require_roles("ADMIN")
def reset_password(user_id):
    data = PasswordIn(**(request.get_json(silent=True) or {}))
    user_service.admin_reset_password(user_id, data.password)
    return jsonify(ok=True)
```

- [ ] **Step 6: Register the blueprint**

`backend/app/__init__.py` — after the auth blueprint registration:
```python
    from .blueprints.users import bp as users_bp
    app.register_blueprint(users_bp)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_users_api.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas backend/app/services/user_service.py backend/app/blueprints/users.py backend/app/__init__.py backend/tests/test_users_api.py
git commit -m "feat(backend): users admin API (list/create/update/reset-password)"
```

---

### Task 3: Divisions API

**Files:**
- Create: `backend/app/schemas/division.py`
- Create: `backend/app/services/division_service.py`
- Create: `backend/app/blueprints/divisions.py`
- Modify: `backend/app/__init__.py` (register blueprint)
- Test: `backend/tests/test_divisions_api.py`

**Interfaces:**
- Produces:
  - Service: `list_divisions()`, `create_division(*, number, name)`, `update_division(division_id, *, number, name, active, l1_approver_id)`.
  - Endpoints (ADMIN): `GET/POST /api/divisions`, `PATCH /api/divisions/<id>`.
  - Division JSON: `{id, number, name, active, l1_approver_id}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_divisions_api.py`:
```python
from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _admin(client):
    db.session.add(User(username="admin", email="a@x.com", name="Admin",
                        password_hash=hash_password("secret123"), roles='["ADMIN"]'))
    db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})


def test_list_requires_admin(client):
    assert client.get("/api/divisions").status_code == 401


def test_create_list_update_division(client, app):
    _admin(client)
    created = client.post("/api/divisions", json={"number": "100", "name": "Field Services"})
    assert created.status_code == 201
    div = created.get_json()
    assert div["number"] == "100" and div["active"] is True

    listing = client.get("/api/divisions").get_json()
    assert any(d["number"] == "100" for d in listing)

    updated = client.patch(f"/api/divisions/{div['id']}", json={
        "number": "100", "name": "Field Svcs", "active": False, "l1_approver_id": None})
    assert updated.status_code == 200
    assert updated.get_json()["name"] == "Field Svcs"
    assert updated.get_json()["active"] is False


def test_duplicate_number_conflicts(client, app):
    _admin(client)
    assert client.post("/api/divisions", json={"number": "200", "name": "A"}).status_code == 201
    assert client.post("/api/divisions", json={"number": "200", "name": "B"}).status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_divisions_api.py -v`
Expected: FAIL — 404 / import error.

- [ ] **Step 3: Write the schemas**

`backend/app/schemas/division.py`:
```python
from pydantic import BaseModel, Field


class DivisionCreate(BaseModel):
    number: str = Field(min_length=1)
    name: str = Field(min_length=1)


class DivisionUpdate(BaseModel):
    number: str = Field(min_length=1)
    name: str = Field(min_length=1)
    active: bool = True
    l1_approver_id: str | None = None
```

- [ ] **Step 4: Write the service**

`backend/app/services/division_service.py`:
```python
from app.extensions import db
from app.models import Division
from app.services.errors import ServiceError


def list_divisions():
    return db.session.query(Division).order_by(Division.number).all()


def create_division(*, number, name):
    num = number.strip()
    if db.session.query(Division).filter_by(number=num).first() is not None:
        raise ServiceError("Division number already exists.", 409)
    div = Division(number=num, name=name.strip())
    db.session.add(div)
    db.session.commit()
    return div


def update_division(division_id, *, number, name, active, l1_approver_id):
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
    div.l1_approver_id = l1_approver_id or None
    db.session.commit()
    return div
```

- [ ] **Step 5: Write the blueprint**

`backend/app/blueprints/divisions.py`:
```python
from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.division import DivisionCreate, DivisionUpdate
from app.services import division_service

bp = Blueprint("divisions", __name__, url_prefix="/api/divisions")


def division_out(d):
    return {
        "id": d.id, "number": d.number, "name": d.name,
        "active": d.active, "l1_approver_id": d.l1_approver_id,
    }


@bp.get("")
@require_roles("ADMIN")
def list_divisions():
    return jsonify([division_out(d) for d in division_service.list_divisions()])


@bp.post("")
@require_roles("ADMIN")
def create_division():
    data = DivisionCreate(**(request.get_json(silent=True) or {}))
    div = division_service.create_division(**data.model_dump())
    return jsonify(division_out(div)), 201


@bp.patch("/<division_id>")
@require_roles("ADMIN")
def update_division(division_id):
    data = DivisionUpdate(**(request.get_json(silent=True) or {}))
    div = division_service.update_division(division_id, **data.model_dump())
    return jsonify(division_out(div))
```

- [ ] **Step 6: Register the blueprint**

`backend/app/__init__.py` — after the users blueprint:
```python
    from .blueprints.divisions import bp as divisions_bp
    app.register_blueprint(divisions_bp)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_divisions_api.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/division.py backend/app/services/division_service.py backend/app/blueprints/divisions.py backend/app/__init__.py backend/tests/test_divisions_api.py
git commit -m "feat(backend): divisions admin API (list/create/update)"
```

---

### Task 4: Approval Thresholds API

**Files:**
- Create: `backend/app/schemas/threshold.py`
- Create: `backend/app/services/threshold_service.py`
- Create: `backend/app/blueprints/thresholds.py`
- Modify: `backend/app/__init__.py` (register blueprint)
- Test: `backend/tests/test_thresholds_api.py`

**Interfaces:**
- Produces:
  - Service: `list_thresholds()` (returns the three levels, creating any missing), `set_thresholds(items)` where each item is `{level, max_amount, approver_id}`.
  - Endpoints (ADMIN): `GET /api/thresholds`, `PUT /api/thresholds`.
  - Threshold JSON: `{level, max_amount (str|null), approver_id}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_thresholds_api.py`:
```python
from app.extensions import db
from app.models import User
from app.services.security import hash_password


def _admin(client):
    db.session.add(User(username="admin", email="a@x.com", name="Admin",
                        password_hash=hash_password("secret123"), roles='["ADMIN"]'))
    db.session.commit()
    client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})


def test_get_requires_admin(client):
    assert client.get("/api/thresholds").status_code == 401


def test_get_returns_three_levels(client, app):
    _admin(client)
    body = client.get("/api/thresholds").get_json()
    assert [t["level"] for t in body] == [1, 2, 3]


def test_put_updates_thresholds(client, app):
    _admin(client)
    r = client.put("/api/thresholds", json={"thresholds": [
        {"level": 1, "max_amount": "50000", "approver_id": None},
        {"level": 2, "max_amount": "250000", "approver_id": None},
        {"level": 3, "max_amount": None, "approver_id": None},
    ]})
    assert r.status_code == 200
    body = r.get_json()
    lvl1 = next(t for t in body if t["level"] == 1)
    lvl3 = next(t for t in body if t["level"] == 3)
    assert lvl1["max_amount"] == "50000"
    assert lvl3["max_amount"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_thresholds_api.py -v`
Expected: FAIL — 404 / import error.

- [ ] **Step 3: Write the schemas**

`backend/app/schemas/threshold.py`:
```python
from decimal import Decimal

from pydantic import BaseModel


class ThresholdIn(BaseModel):
    level: int
    max_amount: Decimal | None = None
    approver_id: str | None = None


class ThresholdsUpdate(BaseModel):
    thresholds: list[ThresholdIn]
```

- [ ] **Step 4: Write the service**

`backend/app/services/threshold_service.py`:
```python
from app.extensions import db
from app.models import ApprovalThreshold
from app.services.errors import ServiceError


def list_thresholds():
    existing = {t.level: t for t in db.session.query(ApprovalThreshold).all()}
    for level in (1, 2, 3):
        if level not in existing:
            t = ApprovalThreshold(level=level, max_amount=None, approver_id=None)
            db.session.add(t)
            existing[level] = t
    db.session.commit()
    return [existing[level] for level in (1, 2, 3)]


def set_thresholds(items):
    by_level = {t.level: t for t in list_thresholds()}
    for item in items:
        if item["level"] not in (1, 2, 3):
            raise ServiceError("Invalid threshold level.")
        row = by_level[item["level"]]
        row.max_amount = item["max_amount"]
        row.approver_id = item["approver_id"] or None
    db.session.commit()
    return [by_level[level] for level in (1, 2, 3)]
```

- [ ] **Step 5: Write the blueprint**

`backend/app/blueprints/thresholds.py`:
```python
from flask import Blueprint, jsonify, request

from app.authz import require_roles
from app.schemas.threshold import ThresholdsUpdate
from app.services import threshold_service

bp = Blueprint("thresholds", __name__, url_prefix="/api/thresholds")


def threshold_out(t):
    return {
        "level": t.level,
        "max_amount": str(t.max_amount) if t.max_amount is not None else None,
        "approver_id": t.approver_id,
    }


@bp.get("")
@require_roles("ADMIN")
def get_thresholds():
    return jsonify([threshold_out(t) for t in threshold_service.list_thresholds()])


@bp.put("")
@require_roles("ADMIN")
def put_thresholds():
    data = ThresholdsUpdate(**(request.get_json(silent=True) or {}))
    items = [t.model_dump() for t in data.thresholds]
    rows = threshold_service.set_thresholds(items)
    return jsonify([threshold_out(t) for t in rows])
```

- [ ] **Step 6: Register the blueprint**

`backend/app/__init__.py` — after the divisions blueprint:
```python
    from .blueprints.thresholds import bp as thresholds_bp
    app.register_blueprint(thresholds_bp)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_thresholds_api.py -v`
Expected: all 3 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/threshold.py backend/app/services/threshold_service.py backend/app/blueprints/thresholds.py backend/app/__init__.py backend/tests/test_thresholds_api.py
git commit -m "feat(backend): approval thresholds admin API (get/put)"
```

---

### Task 5: Profile API (change password, set delegate)

**Files:**
- Create: `backend/app/schemas/profile.py`
- Create: `backend/app/services/profile_service.py`
- Create: `backend/app/blueprints/profile.py`
- Modify: `backend/app/__init__.py` (register blueprint)
- Test: `backend/tests/test_profile_api.py`

**Interfaces:**
- Produces:
  - Service: `change_password(user_id, current, new)`, `set_delegate(user_id, delegate_id)`.
  - Endpoints (login required, self): `GET /api/profile`, `PATCH /api/profile` (delegate), `POST /api/profile/password`.
  - Profile JSON: `{id, username, name, email, roles, division_id, delegate_id}`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_profile_api.py`:
```python
from app.extensions import db
from app.models import User
from app.services.security import hash_password, verify_password


def _user(client, username="u", password="secret123"):
    u = User(username=username, email=f"{username}@x.com", name=username.upper(),
             password_hash=hash_password(password), roles='["REQUESTOR"]')
    db.session.add(u)
    db.session.commit()
    client.post("/api/auth/login", json={"username": username, "password": password})
    return u


def test_profile_requires_auth(client):
    assert client.get("/api/profile").status_code == 401


def test_get_profile(client, app):
    _user(client)
    body = client.get("/api/profile").get_json()
    assert body["username"] == "u" and "delegate_id" in body


def test_change_password(client, app):
    u = _user(client)
    r = client.post("/api/profile/password",
                    json={"current_password": "secret123", "new_password": "newsecret123"})
    assert r.status_code == 200
    refreshed = db.session.get(User, u.id)
    assert verify_password("newsecret123", refreshed.password_hash)


def test_change_password_wrong_current(client, app):
    _user(client)
    r = client.post("/api/profile/password",
                    json={"current_password": "WRONG", "new_password": "newsecret123"})
    assert r.status_code == 400


def test_set_delegate(client, app):
    u = _user(client)
    other = User(username="d", email="d@x.com", name="D",
                 password_hash=hash_password("secret123"), roles='["APPROVER"]')
    db.session.add(other)
    db.session.commit()
    r = client.patch("/api/profile", json={"delegate_id": other.id})
    assert r.status_code == 200
    assert db.session.get(User, u.id).delegate_id == other.id


def test_cannot_delegate_to_self(client, app):
    u = _user(client)
    assert client.patch("/api/profile", json={"delegate_id": u.id}).status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_profile_api.py -v`
Expected: FAIL — 404 / import error.

- [ ] **Step 3: Write the schemas**

`backend/app/schemas/profile.py`:
```python
from pydantic import BaseModel, Field


class DelegateIn(BaseModel):
    delegate_id: str | None = None


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
```

- [ ] **Step 4: Write the service**

`backend/app/services/profile_service.py`:
```python
from app.extensions import db
from app.models import User
from app.services.errors import ServiceError
from app.services.security import verify_password, hash_password


def change_password(user_id, current, new):
    user = db.session.get(User, user_id)
    if not verify_password(current, user.password_hash):
        raise ServiceError("Current password is incorrect.")
    user.password_hash = hash_password(new)
    db.session.commit()


def set_delegate(user_id, delegate_id):
    user = db.session.get(User, user_id)
    if delegate_id:
        if delegate_id == user_id:
            raise ServiceError("You cannot delegate to yourself.")
        if db.session.get(User, delegate_id) is None:
            raise ServiceError("Delegate not found.", 404)
    user.delegate_id = delegate_id or None
    db.session.commit()
    return user
```

- [ ] **Step 5: Write the blueprint**

`backend/app/blueprints/profile.py`:
```python
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.schemas.profile import DelegateIn, ChangePasswordIn
from app.services import profile_service

bp = Blueprint("profile", __name__, url_prefix="/api/profile")


def profile_out(u):
    return {
        "id": u.id, "username": u.username, "name": u.name, "email": u.email,
        "roles": u.roles_list, "division_id": u.division_id, "delegate_id": u.delegate_id,
    }


@bp.get("")
@login_required
def get_profile():
    return jsonify(profile_out(current_user))


@bp.patch("")
@login_required
def set_delegate():
    data = DelegateIn(**(request.get_json(silent=True) or {}))
    user = profile_service.set_delegate(current_user.id, data.delegate_id)
    return jsonify(profile_out(user))


@bp.post("/password")
@login_required
def change_password():
    data = ChangePasswordIn(**(request.get_json(silent=True) or {}))
    profile_service.change_password(current_user.id, data.current_password, data.new_password)
    return jsonify(ok=True)
```

- [ ] **Step 6: Register the blueprint**

`backend/app/__init__.py` — after the thresholds blueprint:
```python
    from .blueprints.profile import bp as profile_bp
    app.register_blueprint(profile_bp)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_profile_api.py -v`
Expected: all 6 tests PASS.

- [ ] **Step 8: Run the full suite (no regressions)**

Run: `pytest -q`
Expected: all backend tests pass (M1 + M2 + M4).

- [ ] **Step 9: Commit**

```bash
git add backend/app/schemas/profile.py backend/app/services/profile_service.py backend/app/blueprints/profile.py backend/app/__init__.py backend/tests/test_profile_api.py
git commit -m "feat(backend): profile API (change password, set delegate)"
```

---

## Self-Review

**Spec coverage (spec §5 roles/workflow admin surface, §6 admin/profile endpoints, §14 M4 slice):**
- Role-based authorization (401/403) → Task 1. ✓
- Users management (list/create/update/reset-password, roles, division, active) → Task 2. ✓
- Divisions (list/create/update, number/name/active/L1 approver) → Task 3. ✓
- Approval thresholds (3 levels, max amounts, approvers; get/put) → Task 4. ✓
- Profile (change password, set delegate) → Task 5. ✓
- Pydantic validation on all request bodies; ValidationError → 400 → Task 1 handler + per-domain schemas. ✓
- The admin/profile **UI** is M5 (this milestone is backend only, verified by pytest).
- Password reset **by email** remains deferred (needs the M-email adapter); admin reset-password (Task 2) and self change-password (Task 5) are covered.

**Placeholder scan:** No TBD/TODO; every step has complete code + expected output. Empty `schemas/__init__.py` marker is intentional. ✓

**Type consistency:** `ServiceError(message, status)` used uniformly; `require_roles` used on every admin endpoint; service function signatures match their `model_dump()` callers (e.g. `create_user(**UserCreate().model_dump())` — fields `username,email,name,password,roles,division_id` align). Output serializers use `roles_list` (not the raw `roles` string). Threshold `max_amount` serialized as str|null consistently. Profile endpoints use `current_user.id`. ✓
