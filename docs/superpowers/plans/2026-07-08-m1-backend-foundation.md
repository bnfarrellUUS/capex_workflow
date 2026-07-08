# M1 — Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Flask backend skeleton — app factory, config, the full SQLAlchemy data model ported from the current Prisma schema, migrations, and a dev seed — then remove the old Next.js `capex-app`.

**Architecture:** A Flask app-factory backend under `backend/`, layered blueprint → service → model. SQLAlchemy 2.x models (typed `Mapped`) reproduce the existing database schema table-for-table. Alembic (via Flask-Migrate) manages schema; a seed script recreates the dev admin, divisions, and thresholds. This milestone is the foundation every later milestone builds on.

**Tech Stack:** Python 3.11+, Flask 3.x, Flask-SQLAlchemy 3.1+, SQLAlchemy 2.x, Flask-Migrate/Alembic, Pydantic v2 (used from M4), bcrypt, pytest. SQLite for dev/test; Azure SQL Server (`mssql+pyodbc`) for prod.

## Global Constraints

- **Python** 3.11+. **Flask** 3.x. **SQLAlchemy** 2.x (typed `Mapped`/`mapped_column`). **Flask-SQLAlchemy** 3.1+.
- **Databases:** SQLite for dev/test; Azure SQL Server for test/prod via the `mssql+pyodbc` dialect. **Avoid provider-specific features** so both behave identically.
- **Roles** stored as a JSON string column; default `["REQUESTOR"]`. **Statuses/actions** stored as validated strings, never DB enums.
- **Money** fields use `Numeric`/`Decimal`.
- **IDs** are opaque strings (`uuid4().hex`). Request numbers are `CX######` (allocated later, M5).
- **Styling (all later UI):** brand color palette only — navy `#0B2A4A`, blue `#2E6DF0`, sky `#8FB2FF`. No logo mark, no custom favicon, no special typeface.
- **The old `capex-app` (Next.js) is deleted** at the end of this milestone, after the schema is ported.
- All API routes are namespaced under `/api`.

---

### Task 1: Backend scaffold, app factory, config, health endpoint

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/pytest.ini`
- Create: `backend/.flaskenv`
- Create: `backend/wsgi.py`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/extensions.py`
- Create: `backend/app/blueprints/__init__.py`
- Create: `backend/app/blueprints/health.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `app.extensions.db` — the `SQLAlchemy` instance (imported everywhere models are defined).
  - `app.extensions.migrate` — the `Migrate` instance.
  - `app.create_app(config_object=None) -> Flask` — the app factory.
  - `app.config.DevConfig`, `TestConfig`, `ProdConfig` — config classes.
  - `GET /api/health` → `{"status": "ok"}`.

- [ ] **Step 1: Create dependency and tooling files**

`backend/requirements.txt`:
```
Flask>=3.0,<4.0
Flask-SQLAlchemy>=3.1,<4.0
Flask-Migrate>=4.0,<5.0
SQLAlchemy>=2.0,<3.0
pydantic>=2.6,<3.0
python-dotenv>=1.0
bcrypt>=4.1
pytest>=8.0
```

`backend/pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

`backend/.flaskenv`:
```
FLASK_APP=wsgi.py
FLASK_DEBUG=1
```

`backend/wsgi.py`:
```python
from app import create_app

app = create_app()
```

- [ ] **Step 2: Write the config module**

`backend/app/config.py`:
```python
import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///capex_dev.db"
    )


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class ProdConfig(BaseConfig):
    # e.g. mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server
    # Read lazily (via .get) so importing the module never fails when the var
    # is unset in dev/test; deployment must set DATABASE_URL.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
```

- [ ] **Step 3: Write the extensions module**

`backend/app/extensions.py`:
```python
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
```

- [ ] **Step 4: Write the health blueprint**

`backend/app/blueprints/__init__.py`:
```python
```
(empty package marker)

`backend/app/blueprints/health.py`:
```python
from flask import Blueprint, jsonify

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    return jsonify(status="ok")
```

- [ ] **Step 5: Write the app factory**

`backend/app/__init__.py`:
```python
from flask import Flask

from .config import DevConfig
from .extensions import db, migrate


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or DevConfig)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so their tables register on the metadata.
    from app import models  # noqa: F401

    from .blueprints.health import bp as health_bp
    app.register_blueprint(health_bp)

    return app
```

Note: `app/models/__init__.py` is created in Task 2. Until then this import fails, so run this task's test only after Task 2 — OR create a temporary empty `backend/app/models/__init__.py` now and fill it in Task 2. Create the empty file now:

`backend/app/models/__init__.py`:
```python
```

- [ ] **Step 6: Write the test fixtures and health test**

`backend/tests/__init__.py`:
```python
```
(empty package marker)

`backend/tests/conftest.py`:
```python
import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
```

`backend/tests/test_health.py`:
```python
def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
```

- [ ] **Step 7: Create a virtualenv, install, and run the test to verify it passes**

Run (from `backend/`, using Git Bash because the repo path contains `&`):
```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv/bin/activate on POSIX
pip install -r requirements.txt
pytest tests/test_health.py -v
```
Expected: `test_health_ok PASSED`.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat(backend): Flask app factory, config, health endpoint"
```

---

### Task 2: SQLAlchemy data model (schema port)

**Files:**
- Modify: `backend/app/models/__init__.py` (replace the empty placeholder)
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/security.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.extensions.db`, `Base` (Task 1).
- Produces (all importable from `app.models`):
  - `User, Division, ApprovalThreshold, CapexRequest, EquipmentItem, Attachment, ApprovalAction, NotificationLog, Counter, AppSetting`
  - Key columns/relationships used by later milestones: `User.roles` (JSON string), `User.division`/`Division.users`, `User.delegate`/`User.delegates_for`, `Division.l1_approver`, `CapexRequest.equipment_items` (cascade delete), `CapexRequest.requestor`/`assignee`/`division`, `CapexRequest.status` (default `"DRAFT"`), `CapexRequest.total_cost`/`required_levels`/`current_level`.
  - `app.services.security.hash_password(pw: str) -> str`, `verify_password(pw: str, hashed: str) -> bool`.

- [ ] **Step 1: Write the failing model test**

`backend/tests/test_models.py`:
```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ImportError` / `cannot import name 'User'`.

- [ ] **Step 3: Write the security helper**

`backend/app/services/__init__.py`:
```python
```
(empty package marker)

`backend/app/services/security.py`:
```python
import bcrypt


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
```

- [ ] **Step 4: Write the models**

`backend/app/models/__init__.py` (replace the empty file):
```python
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Boolean, Integer, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


def _id() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    username: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    roles: Mapped[str] = mapped_column(String, default='["REQUESTOR"]')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    division_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("divisions.id", ondelete="NO ACTION"), nullable=True
    )
    division: Mapped[Optional["Division"]] = relationship(
        back_populates="users", foreign_keys=[division_id]
    )

    delegate_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    delegate: Mapped[Optional["User"]] = relationship(
        "User", remote_side=[id], back_populates="delegates_for"
    )
    delegates_for: Mapped[list["User"]] = relationship(
        "User", back_populates="delegate"
    )

    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reset_token: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    reset_token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )


class Division(db.Model):
    __tablename__ = "divisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    number: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    l1_approver_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION", use_alter=True, name="fk_division_l1_approver"),
        nullable=True,
    )
    l1_approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[l1_approver_id]
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="division", foreign_keys="User.division_id"
    )


class ApprovalThreshold(db.Model):
    __tablename__ = "approval_thresholds"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    level: Mapped[int] = mapped_column(Integer, unique=True)  # 1, 2, 3
    max_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    approver_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_id])


class CapexRequest(db.Model):
    __tablename__ = "capex_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    number: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="DRAFT")

    requestor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"))
    requestor: Mapped["User"] = relationship("User", foreign_keys=[requestor_id])
    assignee_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_id])
    division_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("divisions.id", ondelete="NO ACTION"), nullable=True
    )
    division: Mapped[Optional["Division"]] = relationship("Division")
    request_date: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # Basic info
    description: Mapped[str] = mapped_column(Text, default="")
    budgeted: Mapped[bool] = mapped_column(Boolean, default=False)
    replacement: Mapped[bool] = mapped_column(Boolean, default=False)
    health_safety: Mapped[bool] = mapped_column(Boolean, default=False)
    revenue_generating: Mapped[bool] = mapped_column(Boolean, default=False)
    environmental: Mapped[bool] = mapped_column(Boolean, default=False)
    competitive_bids: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_recommended: Mapped[bool] = mapped_column(Boolean, default=False)

    # Narrative
    justification: Mapped[str] = mapped_column(Text, default="")
    effect_on_operations: Mapped[str] = mapped_column(Text, default="")

    # Economic justification
    asset_life: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    irr_after_tax: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    first_year_ebit: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    annual_savings: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    payback_years: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    npv_savings: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)

    # Finance section (completed after final approval)
    cost_autos_trucks: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    cost_machinery: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    cost_improvements: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    cost_furniture: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    cost_permits: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    cost_misc: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    finance_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    total_cost: Mapped[Decimal] = mapped_column(Numeric, default=0)
    required_levels: Mapped[int] = mapped_column(Integer, default=1)
    current_level: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    equipment_items: Mapped[list["EquipmentItem"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
    actions: Mapped[list["ApprovalAction"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class EquipmentItem(db.Model):
    __tablename__ = "equipment_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="CASCADE")
    )
    request: Mapped["CapexRequest"] = relationship(back_populates="equipment_items")
    units: Mapped[int] = mapped_column(Integer)
    condition: Mapped[str] = mapped_column(String)  # "NEW" | "USED"
    type: Mapped[str] = mapped_column(String)
    make: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    cost: Mapped[Decimal] = mapped_column(Numeric)


class Attachment(db.Model):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="CASCADE")
    )
    request: Mapped["CapexRequest"] = relationship(back_populates="attachments")
    filename: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"))
    uploaded_by: Mapped["User"] = relationship("User")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ApprovalAction(db.Model):
    __tablename__ = "approval_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="CASCADE")
    )
    request: Mapped["CapexRequest"] = relationship(back_populates="actions")
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="NO ACTION"))
    actor: Mapped["User"] = relationship("User", foreign_keys=[actor_id])
    acted_for_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.id", ondelete="NO ACTION"), nullable=True
    )
    action: Mapped[str] = mapped_column(String)  # SUBMITTED | APPROVED | REJECTED | RESUBMITTED | FINANCE_COMPLETED
    level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class NotificationLog(db.Model):
    __tablename__ = "notification_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    request_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("capex_requests.id", ondelete="SET NULL"), nullable=True
    )
    recipient: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)  # ASSIGNED | DECIDED | FINANCE_READY | REMINDER
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Counter(db.Model):
    __tablename__ = "counters"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[int] = mapped_column(Integer)


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
```

- [ ] **Step 5: Run the model test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: all four tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models backend/app/services backend/tests/test_models.py
git commit -m "feat(backend): SQLAlchemy data model ported from Prisma schema"
```

---

### Task 3: Alembic migrations (Flask-Migrate)

**Files:**
- Create: `backend/migrations/` (generated by `flask db init`)
- Create: `backend/migrations/versions/<hash>_initial_schema.py` (generated)

**Interfaces:**
- Consumes: `create_app`, `db`, all models (Tasks 1–2).
- Produces: a working `flask db upgrade` that builds the full schema on an empty database.

- [ ] **Step 1: Initialize the migrations folder**

Run (from `backend/`, venv active, `FLASK_APP` from `.flaskenv`):
```bash
flask db init
```
Expected: creates `backend/migrations/`.

- [ ] **Step 2: Generate the initial migration**

Run:
```bash
flask db migrate -m "initial schema"
```
Expected: a file appears under `migrations/versions/` containing `op.create_table("users", ...)` for all ten tables. Open it and confirm every table from Task 2 is present.

- [ ] **Step 3: Apply the migration to a fresh dev DB**

Run:
```bash
rm -f instance/capex_dev.db
flask db upgrade
```
Expected: `Running upgrade -> <hash>, initial schema`, no errors, and `instance/capex_dev.db` now exists.

- [ ] **Step 4: Verify tables exist**

Run:
```bash
python -c "import sqlite3; c=sqlite3.connect('instance/capex_dev.db'); print(sorted(r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")))"
```
Expected output includes: `app_settings, approval_actions, approval_thresholds, attachments, capex_requests, counters, divisions, equipment_items, notification_logs, users` (plus `alembic_version`).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations
git commit -m "feat(backend): initial Alembic migration for full schema"
```

---

### Task 4: Dev seed script

**Files:**
- Create: `backend/seed.py`
- Test: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: `create_app`, `db`, models, `app.services.security.hash_password`.
- Produces: `seed.py` with `seed(session) -> None` that creates (idempotently) the admin user, sample divisions, and the three approval thresholds. Running `python seed.py` seeds the dev DB.
- Seed data (parity with the current app): admin username `admin`, email `admin@uniteduptime.com`, name `Administrator`, password `ChangeMe123!`, roles `["ADMIN","REQUESTOR","APPROVER","FINANCE"]`.

- [ ] **Step 1: Write the failing seed test**

`backend/tests/test_seed.py`:
```python
from app.extensions import db
from app.models import User, Division, ApprovalThreshold
from app.services.security import verify_password
from seed import seed


def test_seed_creates_admin(app):
    seed(db.session)
    admin = db.session.query(User).filter_by(username="admin").one()
    assert "ADMIN" in admin.roles
    assert verify_password("ChangeMe123!", admin.password_hash)


def test_seed_creates_divisions_and_thresholds(app):
    seed(db.session)
    assert db.session.query(Division).count() >= 1
    assert db.session.query(ApprovalThreshold).count() == 3


def test_seed_is_idempotent(app):
    seed(db.session)
    seed(db.session)
    assert db.session.query(User).filter_by(username="admin").count() == 1
    assert db.session.query(ApprovalThreshold).count() == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_seed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'seed'` or `ImportError`.

- [ ] **Step 3: Write the seed script**

`backend/seed.py`:
```python
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models import User, Division, ApprovalThreshold
from app.services.security import hash_password


def _get_or_create(session, model, defaults=None, **key):
    obj = session.query(model).filter_by(**key).one_or_none()
    if obj is not None:
        return obj
    obj = model(**key, **(defaults or {}))
    session.add(obj)
    session.flush()
    return obj


def seed(session) -> None:
    _get_or_create(
        session, User,
        username="admin",
        defaults={
            "email": "admin@uniteduptime.com",
            "name": "Administrator",
            "password_hash": hash_password("ChangeMe123!"),
            "roles": '["ADMIN","REQUESTOR","APPROVER","FINANCE"]',
        },
    )
    _get_or_create(session, Division, number="100", defaults={"name": "Field Services"})
    _get_or_create(session, Division, number="200", defaults={"name": "Corporate"})
    _get_or_create(session, ApprovalThreshold, level=1, defaults={"max_amount": Decimal("50000")})
    _get_or_create(session, ApprovalThreshold, level=2, defaults={"max_amount": Decimal("250000")})
    _get_or_create(session, ApprovalThreshold, level=3, defaults={"max_amount": None})
    session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed(db.session)
        print("Seed complete.")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_seed.py -v`
Expected: all three tests PASS.

- [ ] **Step 5: Seed the dev database and verify**

Run:
```bash
python seed.py
```
Expected: `Seed complete.` Then confirm:
```bash
python -c "import sqlite3; c=sqlite3.connect('instance/capex_dev.db'); print(c.execute('select username from users').fetchall())"
```
Expected: `[('admin',)]`.

- [ ] **Step 6: Commit**

```bash
git add backend/seed.py backend/tests/test_seed.py
git commit -m "feat(backend): dev seed for admin, divisions, thresholds"
```

---

### Task 5: Remove the old Next.js app and finalize repo hygiene

**Files:**
- Delete: `capex-app/` (entire directory)
- Create: `backend/.gitignore`
- Create: `backend/README.md`
- Modify: root `.gitignore` (create if absent)

**Interfaces:**
- Consumes: nothing at runtime.
- Produces: a repo with only the new `backend/` (frontend arrives in M3); no `capex-app`.

- [ ] **Step 1: Confirm the schema is fully ported before deleting**

Run: `pytest -v` (from `backend/`)
Expected: all tests from Tasks 1, 2, 4 PASS. Do NOT proceed if any fail — the schema port must be complete first.

- [ ] **Step 2: Write backend ignore rules**

`backend/.gitignore`:
```
.venv/
__pycache__/
*.pyc
instance/
uploads/
.env
*.db
```

- [ ] **Step 3: Write the backend README**

`backend/README.md`:
```markdown
# CAPEX Backend (Flask)

## Setup (Git Bash — the repo path contains `&`, so use Git Bash, not cmd/PowerShell)

    cd backend
    python -m venv .venv
    source .venv/Scripts/activate
    pip install -r requirements.txt
    flask db upgrade
    python seed.py

## Run

    flask run          # http://localhost:5000  (GET /api/health -> {"status":"ok"})

## Test

    pytest -v

Dev login (after seed): admin / ChangeMe123!
```

- [ ] **Step 4: Remove the old app**

Run (from repo root):
```bash
git rm -r capex-app
```
Expected: the entire Next.js app is staged for deletion.

- [ ] **Step 5: Verify nothing else references capex-app**

Run (from repo root):
```bash
grep -rIl "capex-app" --exclude-dir=.git --exclude-dir=node_modules . || echo "no references"
```
Expected: only design/spec/plan docs may mention it historically; no build or config file depends on it. This is acceptable.

- [ ] **Step 6: Commit**

```bash
git add backend/.gitignore backend/README.md .gitignore
git commit -m "chore: remove Next.js capex-app; add backend gitignore and README"
```

---

## Self-Review

**Spec coverage (M1 slice of spec §2, §4, §13):**
- App factory / config / extensions → Task 1. ✓
- Full SQLAlchemy schema port (all 10 tables, roles-as-JSON, statuses-as-strings, Numeric money, cascade/NoAction/SetNull FKs) → Task 2. ✓
- Migrations (Alembic/Flask-Migrate, SQLite dev) → Task 3. ✓
- Seed (admin/divisions/thresholds, bcrypt hash) → Task 4. ✓
- Remove `capex-app` after schema port (spec §14 step 1) → Task 5, gated by Step 1 re-running the full suite. ✓
- Later-milestone items (auth flow, Pydantic schemas, frontend, Azure Blob, SMTP, workflow) are intentionally out of M1.

**Placeholder scan:** No TBD/TODO; every code step contains complete code; commands have expected output. The only "fill later" note is the deliberate empty `app/models/__init__.py` placeholder in Task 1 Step 5, which Task 2 replaces — called out explicitly. ✓

**Type consistency:** Model class names and attributes referenced in tests (`User.roles`, `User.delegate`/`delegates_for`, `CapexRequest.equipment_items`, `EquipmentItem` fields) match the definitions in Task 2. `hash_password`/`verify_password` signatures match between `security.py`, the seed, and the seed test. `seed(session)` signature matches its test usage. ✓

**Cross-DB note:** `ondelete` strings (`"NO ACTION"`, `"CASCADE"`, `"SET NULL"`) are emitted into the migration; on SQLite they are advisory, but they produce the correct DDL for SQL Server (the reason the current Prisma schema set NoAction to avoid multiple-cascade-path errors). Verified against spec §4.
