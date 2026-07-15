# Email-Based Login with Default Password Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sign-in switches from username to email; new/reset accounts start at `Welcome@1` and must set their own password on first login (server-enforced).

**Architecture:** Backend-first in five tasks that each leave the pytest suite green (flag column → email login → set-password + gating → drop username → default-password lifecycle), then three frontend tasks, then docs/verification. Two Alembic migrations (add flag; drop username).

**Tech Stack:** Flask + SQLAlchemy 2.0 + Alembic + Pydantic v2 (backend); React 19 + TanStack Query 5 (frontend). Spec: `docs/superpowers/specs/2026-07-15-email-login-design.md`.

## Global Constraints

- Default password is exactly `Welcome@1`, defined once as `DEFAULT_PASSWORD` in `backend/app/config.py` (`BaseConfig`). Never hardcode it elsewhere in app code (tests may read it from config or literal).
- The 403 gating response body is exactly `{"error": "You must set a new password before continuing.", "code": "PASSWORD_CHANGE_REQUIRED"}`.
- `username` must be gone from: model, DB (via migration), all serializers, all schemas, seed, all tests, all frontend types/components. Email (stored lowercase) is the only identifier.
- Dev seed login: `admin@uniteduptime.com` / `ChangeMe123!`, `must_change_password = False`.
- Windows repo path contains `&` — run frontend tooling via node directly:
  typecheck `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`,
  tests `node ./node_modules/vitest/vitest.mjs run`,
  build `node ./node_modules/vite/bin/vite.js build` (all from `frontend/`).
- Backend tests: from `backend/`: `pytest -q` (activate `.venv` first if needed: `source .venv/Scripts/activate` in bash).
- Commit after each task (message given per task). Keep the suite green at every commit.

---

### Task 1: `must_change_password` flag + `DEFAULT_PASSWORD` config

**Files:**
- Modify: `backend/app/config.py` (BaseConfig)
- Modify: `backend/app/models/__init__.py:49` (User, after `active`)
- Create: `backend/migrations/versions/f7a8b9c0d1e2_add_must_change_password.py`
- Test: `backend/tests/test_models.py` (append)

**Interfaces:**
- Produces: `User.must_change_password: bool` (default False); `app.config["DEFAULT_PASSWORD"] == "Welcome@1"`. Later tasks rely on both names exactly.

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_models.py`:

```python
def test_must_change_password_defaults_false(app):
    u = User(username="flaguser", email="flag@x.com", name="F",
             password_hash="x")
    db.session.add(u)
    db.session.commit()
    assert u.must_change_password is False


def test_default_password_config(app):
    assert app.config["DEFAULT_PASSWORD"] == "Welcome@1"
```

(Match the file's existing imports — it already imports `db` and `User`; check the top of the file and reuse its user-construction style if it differs.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_models.py -q`
Expected: FAIL — `'must_change_password' is an invalid keyword`/AttributeError and KeyError on config.

- [ ] **Step 3: Implement** — in `backend/app/config.py` add to `BaseConfig` (after `SECRET_KEY`):

```python
    # Starting password for new accounts and admin resets; the owner must
    # replace it on first login (User.must_change_password).
    DEFAULT_PASSWORD = "Welcome@1"
```

In `backend/app/models/__init__.py`, after the `active` column on `User`:

```python
    # Set for new accounts and admin resets: the user is gated to the
    # set-password endpoint until they choose their own password.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: Create the migration** — `backend/migrations/versions/f7a8b9c0d1e2_add_must_change_password.py`:

```python
"""add users.must_change_password

Revision ID: f7a8b9c0d1e2
Revises: c5553da9c8ec
Create Date: 2026-07-15

"""
from alembic import op
import sqlalchemy as sa


revision = 'f7a8b9c0d1e2'
down_revision = 'c5553da9c8ec'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('must_change_password')
```

- [ ] **Step 5: Apply migration + run tests**

Run: `cd backend && flask db upgrade && pytest -q`
Expected: upgrade applies; full suite PASSES (154 + 2 new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/models/__init__.py backend/migrations/versions/f7a8b9c0d1e2_add_must_change_password.py backend/tests/test_models.py
git commit -m "feat(auth): must_change_password flag + DEFAULT_PASSWORD config"
```

---

### Task 2: Email-based login (backend)

**Files:**
- Modify: `backend/app/services/auth_service.py:33-39`
- Modify: `backend/app/blueprints/auth.py:10-35`
- Modify: `backend/tests/test_auth_service.py`, `backend/tests/test_auth_api.py`
- Modify (mechanical login-payload sweep): `backend/tests/test_attachments_api.py`, `test_delete_draft.py`, `test_authz.py`, `test_email_settings.py`, `test_divisions_api.py`, `test_email_templates_api.py`, `test_profile_api.py`, `test_request_list.py`, `test_requests_api.py`, `test_thresholds_api.py`, `test_users_api.py`, `test_workflow_api.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `authenticate(email: str, password: str) -> AuthResult` (lookup by `User.email`, lowercased); `POST /api/auth/login` body `{"email", "password"}`; login/`me` JSON gains `"must_change_password": bool` (still includes `username` until Task 4).

- [ ] **Step 1: Update service tests** — in `backend/tests/test_auth_service.py` replace every `authenticate("jdoe", ...)` with `authenticate("j@x.com", ...)`, `authenticate("JDoe", ...)` with `authenticate("J@X.com", ...)` (case-insensitivity now proves email folding), `authenticate("ghost", ...)` with `authenticate("ghost@x.com", ...)`, and `res.user.username == "jdoe"` with `res.user.email == "j@x.com"`. Leave the `_user` helper and `filter_by(username=...)` queries alone for now (column still exists; Task 4 sweeps them).

- [ ] **Step 2: Update API tests** — in `backend/tests/test_auth_api.py` replace each login payload `{"username": "jdoe", "password": ...}` with `{"email": "j@x.com", "password": ...}` and the assertion `r.get_json()["username"] == "jdoe"` with:

```python
    body = r.get_json()
    assert body["email"] == "j@x.com"
    assert body["must_change_password"] is False
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend && pytest tests/test_auth_service.py tests/test_auth_api.py -q`
Expected: FAIL — authenticate still looks up username; login ignores `email` key.

- [ ] **Step 4: Implement** — `backend/app/services/auth_service.py`, replace the head of `authenticate`:

```python
def authenticate(email: str, password: str) -> AuthResult:
    mail = (email or "").strip().lower()
    user = db.session.query(User).filter_by(email=mail).one_or_none()

    if user is None:
        verify_password(password, _DUMMY_HASH)  # equalize timing
        return AuthResult(ok=False, error="Invalid email or password.")
```

…and the wrong-password error string to `"Invalid email or password."`. Update the `_DUMMY_HASH` comment to say "unknown emails" instead of "unknown usernames". Everything else (lockout, counters) unchanged.

`backend/app/blueprints/auth.py`: in `login()` use `authenticate(data.get("email", ""), data.get("password", ""))`; in `_user_json` add `"must_change_password": user.must_change_password,`.

- [ ] **Step 5: Sweep the remaining test logins** — every other test file logs in with a JSON payload. Mechanical rule: `{"username": X, "password": P}` becomes `{"email": <email of that user>, "password": P}`. The email is `f"{X}@x.com"` for users made by `factories.make_user(X)` or created with `email=f"{X}@x.com"`; where the file creates the user explicitly, use that literal email (e.g. `test_users_api.py` creates admin with `email="a@x.com"` → login with `"a@x.com"`). Exact spots (line numbers from before this change):
  - `test_attachments_api.py:12`, `test_delete_draft.py:8`, `test_email_templates_api.py:5`, `test_profile_api.py:11`, `test_requests_api.py:11` — helpers taking a `username` arg: payload becomes `{"email": f"{username}@x.com", "password": ...}`.
  - `test_request_list.py:8`, `test_workflow_api.py:7` — take a user object: `{"email": user.email, "password": "secret123"}`.
  - `test_authz.py:33` → `{"email": "u@x.com", ...}`; `test_email_settings.py:98` → `"admin@x.com"`, `:116` → `"plain@x.com"`; `test_divisions_api.py:10` and `test_thresholds_api.py:10` → the email of the admin user each file creates (open the file and copy it); `test_users_api.py:10,110` → `"a@x.com"`.

- [ ] **Step 6: Run the full suite**

Run: `cd backend && pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/auth_service.py backend/app/blueprints/auth.py backend/tests
git commit -m "feat(auth): login by email instead of username"
```

---

### Task 3: Set-password endpoint + server-side gating

**Files:**
- Create: `backend/app/schemas/auth.py`
- Modify: `backend/app/services/auth_service.py` (append), `backend/app/services/profile_service.py:7-12`
- Modify: `backend/app/blueprints/auth.py`, `backend/app/__init__.py`
- Test: `backend/tests/test_password_change.py` (new)

**Interfaces:**
- Consumes: `User.must_change_password`, `DEFAULT_PASSWORD` (Task 1).
- Produces: `POST /api/auth/set-password` body `{"new_password"}` → 200 with the `_user_json` payload (flag now false); 400 if flag unset, password `< 8` chars, or equal to the default. App-level `before_request` returning the 403 `PASSWORD_CHANGE_REQUIRED` body (Global Constraints) for any blueprint endpoint except `auth.set_password`, `auth.me`, `auth.csrf`, `auth.logout` while the current user is flagged. `auth_service.set_initial_password(user_id, new_password)`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_password_change.py`:

```python
from app.extensions import db
from app.models import User
from app.services.security import hash_password, verify_password


def _flagged_user(app, email="new@x.com"):
    u = User(username=email.split("@")[0], email=email, name="New User",
             password_hash=hash_password(app.config["DEFAULT_PASSWORD"]),
             roles='["REQUESTOR"]', must_change_password=True)
    db.session.add(u)
    db.session.commit()
    return u


def _login(client, app, email="new@x.com"):
    return client.post("/api/auth/login",
                       json={"email": email, "password": app.config["DEFAULT_PASSWORD"]})


def test_login_reports_flag(client, app):
    _flagged_user(app)
    r = _login(client, app)
    assert r.status_code == 200
    assert r.get_json()["must_change_password"] is True


def test_flagged_user_is_gated_to_403(client, app):
    _flagged_user(app)
    _login(client, app)
    r = client.get("/api/requests")
    assert r.status_code == 403
    assert r.get_json()["code"] == "PASSWORD_CHANGE_REQUIRED"


def test_flagged_user_can_still_use_exempt_endpoints(client, app):
    _flagged_user(app)
    _login(client, app)
    assert client.get("/api/auth/me").status_code == 200
    assert client.get("/api/auth/csrf").status_code == 200


def test_set_password_clears_flag_and_unblocks(client, app):
    u = _flagged_user(app)
    _login(client, app)
    r = client.post("/api/auth/set-password", json={"new_password": "MyOwnPass1"})
    assert r.status_code == 200
    assert r.get_json()["must_change_password"] is False
    db.session.refresh(u)
    assert u.must_change_password is False
    assert verify_password("MyOwnPass1", u.password_hash)
    assert client.get("/api/requests").status_code == 200


def test_set_password_rejects_the_default(client, app):
    _flagged_user(app)
    _login(client, app)
    r = client.post("/api/auth/set-password",
                    json={"new_password": app.config["DEFAULT_PASSWORD"]})
    assert r.status_code == 400


def test_set_password_rejects_short(client, app):
    _flagged_user(app)
    _login(client, app)
    assert client.post("/api/auth/set-password",
                       json={"new_password": "short"}).status_code == 400


def test_set_password_requires_flag(client, app):
    u = _flagged_user(app)
    u.must_change_password = False
    db.session.commit()
    _login(client, app)
    assert client.post("/api/auth/set-password",
                       json={"new_password": "MyOwnPass1"}).status_code == 400


def test_logout_stays_available_while_flagged(client, app):
    _flagged_user(app)
    _login(client, app)
    assert client.post("/api/auth/logout").status_code == 200


def test_profile_password_change_clears_flag(client, app):
    u = _flagged_user(app)
    _login(client, app)
    # /api/profile/password is gated while flagged, so clear via set-password
    # first is NOT the point here: flip the flag on directly after a normal
    # change to prove change_password always clears it.
    from app.services import profile_service
    profile_service.change_password(u.id, app.config["DEFAULT_PASSWORD"], "AnotherPass1")
    db.session.refresh(u)
    assert u.must_change_password is False
```

(The `username=` kwarg in `_flagged_user` is removed by Task 4's sweep.)

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_password_change.py -q`
Expected: FAIL — 404 on `/api/auth/set-password`, 200 where 403 expected.

- [ ] **Step 3: Implement.** New `backend/app/schemas/auth.py`:

```python
from pydantic import BaseModel, Field


class SetPasswordIn(BaseModel):
    new_password: str = Field(min_length=8)
```

Append to `backend/app/services/auth_service.py` (add imports `from flask import current_app` and `from app.services.errors import ServiceError`):

```python
def set_initial_password(user_id: str, new_password: str) -> User:
    user = db.session.get(User, user_id)
    if not user.must_change_password:
        raise ServiceError("Password change is not required for this account.")
    if new_password == current_app.config["DEFAULT_PASSWORD"]:
        raise ServiceError("Choose a password different from the default one.")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.session.commit()
    return user
```

In `backend/app/blueprints/auth.py` (`login_required` is already imported; add `from app.schemas.auth import SetPasswordIn` and change the service import to `from app.services.auth_service import authenticate, set_initial_password`):

```python
@bp.post("/set-password")
@login_required
def set_password():
    data = SetPasswordIn(**(request.get_json(silent=True) or {}))
    user = set_initial_password(current_user.id, data.new_password)
    return jsonify(_user_json(user))
```

In `backend/app/__init__.py` (add `request` to the flask import), after `csrf.init_app(app)`:

```python
    # A user flagged must_change_password may only hit the endpoints needed
    # to set a new password (or leave); everything else on the API is 403.
    exempt = {"auth.set_password", "auth.me", "auth.csrf", "auth.logout"}

    @app.before_request
    def _require_password_change():
        from flask_login import current_user
        if (request.blueprint is not None
                and current_user.is_authenticated
                and current_user.must_change_password
                and request.endpoint not in exempt):
            return jsonify(error="You must set a new password before continuing.",
                           code="PASSWORD_CHANGE_REQUIRED"), 403
```

(`request.blueprint is not None` limits this to `/api/*` blueprint routes; the SPA catch-all stays reachable.)

In `backend/app/services/profile_service.py`, `change_password`, before `db.session.commit()`:

```python
    user.must_change_password = False
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest -q`
Expected: full suite PASSES (watch for collateral: no existing test hits an API while flagged, since nothing sets the flag yet).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/services/auth_service.py backend/app/services/profile_service.py backend/app/blueprints/auth.py backend/app/__init__.py backend/tests/test_password_change.py
git commit -m "feat(auth): set-password endpoint + server-enforced change gate"
```

---

### Task 4: Remove `username` from the backend

**Files:**
- Modify: `backend/app/models/__init__.py:44` (delete column), `backend/app/services/user_service.py`, `backend/app/schemas/user.py`, `backend/app/blueprints/users.py:11-15`, `backend/app/blueprints/auth.py:10-18`, `backend/app/blueprints/profile.py:10-14`, `backend/seed.py`
- Create: `backend/migrations/versions/a9b8c7d6e5f4_drop_username.py`
- Modify (sweep): `backend/tests/factories.py` and every test file constructing `User(username=...)` or asserting on `username` — `test_auth_api.py`, `test_auth_service.py`, `test_users_api.py`, `test_models.py`, `test_seed.py`, `test_authz.py`, `test_auth_wiring.py`, `test_email_settings.py`, `test_divisions_api.py`, `test_thresholds_api.py`, `test_workflow_helpers.py`, `test_requests_api.py`, `test_request_list.py`, `test_delete_draft.py`, `test_attachments_api.py`, `test_email_templates_api.py`, `test_profile_api.py`, `test_workflow_api.py`, `test_password_change.py`

**Interfaces:**
- Consumes: email login (Task 2) — nothing may still authenticate by username.
- Produces: `User` without `username`; `create_user(*, email, name, password, roles, division_id)`; `update_user(user_id, *, name, email, roles, division_id, active)`; `user_out`/`_user_json`/`profile_out` without `"username"`; `factories.make_user(key, roles=..., delegate_id=None)` → user with `email=f"{key}@x.com"`, `name=key.title()`; seed keyed on `email="admin@uniteduptime.com"`.

- [ ] **Step 1: Model + serializers + services.** Delete the `username` column from `User`. Remove `"username": u.username,`/`"username": user.username,` entries from `user_out` (`blueprints/users.py`), `_user_json` (`blueprints/auth.py`), `profile_out` (`blueprints/profile.py`). In `user_service.py`:
  - `create_user(*, email, name, password, roles, division_id)` — drop `uname`; clash check becomes `filter(User.email == mail)` with error `"Email already exists."`; construct `User(email=mail, name=name.strip(), password_hash=hash_password(password), roles=serialize_roles(roles), division_id=division_id or None)`.
  - `update_user(...)` — drop the `username=None` parameter and its whole `if username is not None:` block.
  - `list_users()` — order by `User.email` instead of `User.username`.

  In `schemas/user.py`: delete `username` from `UserCreate` and `UserUpdate`.

- [ ] **Step 2: Migration** — `backend/migrations/versions/a9b8c7d6e5f4_drop_username.py`:

```python
"""drop users.username — email is the sole login identifier

Revision ID: a9b8c7d6e5f4
Revises: f7a8b9c0d1e2
Create Date: 2026-07-15

"""
from alembic import op
import sqlalchemy as sa


revision = 'a9b8c7d6e5f4'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "mssql":
        # The initial schema's UNIQUE(username) constraint is unnamed, so SQL
        # Server gave it a generated name; find and drop it before the column.
        rows = bind.exec_driver_sql(
            "SELECT kc.name FROM sys.key_constraints kc "
            "JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id "
            " AND ic.index_id = kc.unique_index_id "
            "JOIN sys.columns c ON c.object_id = ic.object_id "
            " AND c.column_id = ic.column_id "
            "WHERE kc.parent_object_id = OBJECT_ID('users') "
            " AND kc.type = 'UQ' AND c.name = 'username'"
        ).fetchall()
        for (name,) in rows:
            op.execute(f"ALTER TABLE users DROP CONSTRAINT [{name}]")
    # SQLite: batch mode recreates the table, dropping the constraint with it.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('username')


def downgrade():
    # Restored as nullable (original values are gone); uniqueness not restored.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.String(length=150), nullable=True))
```

- [ ] **Step 3: Seed** — `backend/seed.py`, replace the user block:

```python
    _get_or_create(
        session, User,
        email="admin@uniteduptime.com",
        defaults={
            "name": "Administrator",
            "password_hash": hash_password("ChangeMe123!"),
            "roles": '["ADMIN","REQUESTOR","APPROVER","FINANCE"]',
        },
    )
```

- [ ] **Step 4: Factories** — `backend/tests/factories.py`:

```python
def make_user(key, roles='["APPROVER"]', delegate_id=None):
    u = User(email=f"{key}@x.com", name=key.title(),
             password_hash=hash_password("secret123"), roles=roles, delegate_id=delegate_id)
    db.session.add(u)
    db.session.commit()
    return u
```

- [ ] **Step 5: Test sweep.** Run `cd backend && pytest -q 2>&1 | tail -40` and fix every failure with these mechanical rules (then grep to confirm none remain: `grep -rn username backend/app backend/tests backend/seed.py` → only migration files may match):
  1. `User(username="X", email=..., ...)` → drop the `username="X"` kwarg (add `email=f"X@x.com"` if the constructor had none).
  2. `filter_by(username="X")` → `filter_by(email="X@x.com")` (use the file's actual email).
  3. Assertions on `["username"]` / `.username` → the equivalent on `["email"]` / `.email` (e.g. `test_users_api.py` list assertion `any(u["username"] == "jdoe" ...)` → `any(u["email"] == "jdoe@x.com" ...)`).
  4. Create payloads `{"username": ..., "email": ..., "name": ..., "password": ...}` → drop the `"username"` key.
  5. `test_users_api.py` renames/replacements: `test_duplicate_username_conflicts` → `test_duplicate_email_conflicts` (POST the same email twice, expect 409 — drop the changed-email second POST); delete `test_update_can_change_username`; rewrite `test_update_username_duplicate_conflicts` as `test_update_email_duplicate_conflicts` (PATCH user b's email to user a's email, expect 409).
  6. `test_seed.py`: assert on the admin's email `admin@uniteduptime.com` instead of username.
  7. `test_password_change.py`: drop the `username=` kwarg from `_flagged_user`.

- [ ] **Step 6: Apply migration + full suite**

Run: `cd backend && flask db upgrade && pytest -q`
Expected: PASS; `grep -rn "username" backend/app backend/seed.py` returns nothing (migrations excluded).

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat(auth)!: drop username — email is the sole identifier"
```

---

### Task 5: New users and admin resets start at the default password

**Files:**
- Modify: `backend/app/schemas/user.py` (UserCreate, delete PasswordIn), `backend/app/services/user_service.py` (create_user, admin_reset_password), `backend/app/blueprints/users.py:40-45`
- Test: `backend/tests/test_users_api.py` (append/modify)

**Interfaces:**
- Consumes: `DEFAULT_PASSWORD`, `must_change_password`, email login.
- Produces: `POST /api/users` body without `password`; `create_user(*, email, name, roles, division_id)` → user with default password + flag; `POST /api/users/<id>/reset-password` with **no body** calling `user_service.reset_to_default_password(user_id)` (replaces `admin_reset_password`).

- [ ] **Step 1: Write the failing tests** — in `backend/tests/test_users_api.py`, update every create payload to drop `"password"`, then replace `test_short_password_is_validation_error` and `test_admin_reset_password` with:

```python
def test_new_user_gets_default_password_and_flag(client, app):
    _admin(client)
    r = client.post("/api/users", json={
        "email": "fresh@x.com", "name": "Fresh", "roles": ["REQUESTOR"],
        "division_id": None})
    assert r.status_code == 201
    fresh = db.session.query(User).filter_by(email="fresh@x.com").one()
    assert fresh.must_change_password is True
    login = client.post("/api/auth/login", json={
        "email": "fresh@x.com", "password": app.config["DEFAULT_PASSWORD"]})
    assert login.status_code == 200
    assert login.get_json()["must_change_password"] is True


def test_admin_reset_returns_user_to_default(client, app):
    _admin(client)
    created = client.post("/api/users", json={
        "email": "r@x.com", "name": "R", "roles": ["REQUESTOR"]}).get_json()
    # user sets their own password first
    u = db.session.query(User).filter_by(email="r@x.com").one()
    u.password_hash = hash_password("TheirOwn1")
    u.must_change_password = False
    u.failed_logins = 3
    db.session.commit()
    assert client.post(f"/api/users/{created['id']}/reset-password").status_code == 200
    db.session.refresh(u)
    assert u.must_change_password is True
    assert u.failed_logins == 0
    login = client.post("/api/auth/login", json={
        "email": "r@x.com", "password": app.config["DEFAULT_PASSWORD"]})
    assert login.status_code == 200
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_users_api.py -q`
Expected: FAIL — UserCreate requires `password`; reset endpoint requires a body.

- [ ] **Step 3: Implement.** `schemas/user.py`: remove `password` from `UserCreate` and delete the `PasswordIn` class. `user_service.py` (add `from flask import current_app`):

```python
def create_user(*, email, name, roles, division_id):
    if not valid_roles(roles):
        raise ServiceError("Invalid role.")
    mail = email.strip().lower()
    clash = db.session.query(User).filter(User.email == mail).first()
    if clash is not None:
        raise ServiceError("Email already exists.", 409)
    user = User(
        email=mail, name=name.strip(),
        password_hash=hash_password(current_app.config["DEFAULT_PASSWORD"]),
        must_change_password=True,
        roles=serialize_roles(roles), division_id=division_id or None,
    )
    db.session.add(user)
    db.session.commit()
    return user
```

Replace `admin_reset_password` with:

```python
def reset_to_default_password(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise ServiceError("User not found.", 404)
    user.password_hash = hash_password(current_app.config["DEFAULT_PASSWORD"])
    user.must_change_password = True
    user.failed_logins = 0
    user.locked_until = None
    db.session.commit()
    return user
```

`blueprints/users.py`: drop the `PasswordIn` import; the reset route becomes:

```python
@bp.post("/<user_id>/reset-password")
@require_roles("ADMIN")
def reset_password(user_id):
    user_service.reset_to_default_password(user_id)
    return jsonify(ok=True)
```

- [ ] **Step 4: Full suite**

Run: `cd backend && pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/user.py backend/app/services/user_service.py backend/app/blueprints/users.py backend/tests/test_users_api.py
git commit -m "feat(users): new accounts and admin resets start at the default password"
```

---

### Task 6: Frontend — sign in with email

**Files:**
- Modify: `frontend/src/api/auth.ts`, `frontend/src/routes/LoginPage.tsx`, `frontend/src/api/client.test.ts:35-40`

**Interfaces:**
- Consumes: backend `POST /api/auth/login` `{"email","password"}` (Task 2).
- Produces: `CurrentUser` = `{ id, name, email, roles, division_id, must_change_password }` (no `username`); `login(email, password)`. Task 7 reads `must_change_password` from this type.

- [ ] **Step 1: Update `frontend/src/api/auth.ts`:**

```ts
export interface CurrentUser {
  id: string
  name: string
  email: string
  roles: string[]
  division_id: string | null
  must_change_password: boolean
}

export function login(email: string, password: string): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/login', { method: 'POST', body: { email, password } })
}
```

(`fetchMe`/`logout` unchanged.)

- [ ] **Step 2: Update `LoginPage.tsx`** — rename the state/field:

```tsx
  const [email, setEmail] = useState('')
  ...
  mutationFn: () => login(email, password),
  ...
  <div className="space-y-1">
    <label htmlFor="email" className="text-sm font-medium">Email</label>
    <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
      autoComplete="email" required />
  </div>
```

- [ ] **Step 3: Fix fixtures** — `frontend/src/api/client.test.ts` posts `{ username: 'a' }` as an opaque body; change both occurrences to `{ email: 'a' }` so no `username` remains in the frontend tree.

- [ ] **Step 4: Typecheck + tests**

Run (from `frontend/`): `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json && node ./node_modules/vitest/vitest.mjs run`
Expected: tsc clean (if any test mocks a `CurrentUser`, add `must_change_password: false`); vitest PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/routes/LoginPage.tsx frontend/src/api/client.test.ts
git commit -m "feat(web): sign in with email"
```

---

### Task 7: Frontend — forced password-change page

**Files:**
- Modify: `frontend/src/api/client.ts` (ApiError), `frontend/src/api/auth.ts` (setPassword), `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/auth/ProtectedLayout.tsx`, `frontend/src/routes/LoginPage.tsx`
- Create: `frontend/src/routes/ChangePasswordPage.tsx`

**Interfaces:**
- Consumes: `POST /api/auth/set-password` (Task 3); `CurrentUser.must_change_password` (Task 6).
- Produces: route `/change-password`; `ApiError.code?: string`; `setPassword(new_password): Promise<CurrentUser>`.

- [ ] **Step 1: Give `ApiError` a `code`** — `frontend/src/api/client.ts`:

```ts
export class ApiError extends Error {
  status: number
  code?: string
  constructor(status: number, message: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}
```

In both error paths (`api` and `apiUpload`), capture the code:

```ts
    let message = res.statusText
    let code: string | undefined
    try {
      const data = await res.json()
      if (data && data.error) message = data.error
      if (data && data.code) code = data.code
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message, code)
```

- [ ] **Step 2: API + global redirect.** `frontend/src/api/auth.ts`:

```ts
export function setPassword(new_password: string): Promise<CurrentUser> {
  return api<CurrentUser>('/auth/set-password', { method: 'POST', body: { new_password } })
}
```

`frontend/src/main.tsx`, extend `handleAuthError`:

```ts
function handleAuthError(error: unknown) {
  if (!(error instanceof ApiError)) return
  if (error.status === 401 && window.location.pathname !== '/login') {
    window.location.assign(loginPathWithNext(window.location.pathname, window.location.search))
  } else if (error.code === 'PASSWORD_CHANGE_REQUIRED'
      && window.location.pathname !== '/change-password') {
    window.location.assign('/change-password')
  }
}
```

- [ ] **Step 3: The page** — `frontend/src/routes/ChangePasswordPage.tsx` (login-card styling):

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { setPassword } from '../api/auth'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { PasswordInput } from '../components/ui/PasswordInput'
import { Logo } from '../components/Logo'

export default function ChangePasswordPage() {
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => setPassword(newPassword),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      navigate('/', { replace: true })
    },
  })

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (newPassword.length < 8) { setLocalError('Password must be at least 8 characters.'); return }
    if (newPassword !== confirm) { setLocalError('Passwords do not match.'); return }
    setLocalError(null)
    mutation.mutate()
  }

  const error = localError
    ?? (mutation.error instanceof ApiError ? mutation.error.message
      : mutation.error ? 'Could not set the password.' : null)

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-6 shadow-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <Logo size={52} tile className="mb-3" />
          <div className="text-xl font-bold text-fg">Set your new password</div>
          <div className="text-sm text-muted">
            Your account is using the default password — choose your own to continue.
          </div>
        </div>
        <form className="space-y-4" onSubmit={submit}>
          <div className="space-y-1">
            <label htmlFor="new-password" className="text-sm font-medium">New password</label>
            <PasswordInput id="new-password" value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)} autoComplete="new-password" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="confirm-password" className="text-sm font-medium">Confirm new password</label>
            <PasswordInput id="confirm-password" value={confirm}
              onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" required />
          </div>
          {error && <p className="text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving…' : 'Set password'}
          </Button>
        </form>
      </div>
    </main>
  )
}
```

- [ ] **Step 4: Wire routing.** `App.tsx`: `import ChangePasswordPage from './routes/ChangePasswordPage'` and add, next to the login route:

```tsx
      <Route path="/change-password" element={<ChangePasswordPage />} />
```

`ProtectedLayout.tsx`, before `return <AppShell />`:

```tsx
  if (data.must_change_password) return <Navigate to="/change-password" replace />
```

`LoginPage.tsx` `onSuccess`:

```tsx
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      navigate(user.must_change_password ? '/change-password' : safeNext(searchParams.get('next')),
        { replace: true })
    },
```

- [ ] **Step 5: Typecheck + tests + build**

Run (from `frontend/`): `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json && node ./node_modules/vitest/vitest.mjs run && node ./node_modules/vite/bin/vite.js build`
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(web): forced set-your-password page after first login"
```

---

### Task 8: Frontend — admin screens without username, reset-to-default

**Files:**
- Modify: `frontend/src/api/users.ts`, `frontend/src/api/profileApi.ts`, `frontend/src/routes/admin/UserForm.tsx`, `frontend/src/routes/admin/UsersPage.tsx`, `frontend/src/routes/admin/UserEditPage.tsx`, `frontend/src/routes/admin/DivisionForm.tsx:40`, `frontend/src/routes/admin/ThresholdsPage.tsx:61`

**Interfaces:**
- Consumes: Task 5's API (`POST /api/users` without password; bodyless reset).
- Produces: `AdminUser`/`UserInput`/`Profile` without `username`; `resetUserPassword(id: string): Promise<void>`.

- [ ] **Step 1: Types + API** — `frontend/src/api/users.ts`: delete `username` from `AdminUser` and `UserInput`, delete `password` from `UserInput`, and:

```ts
export function resetUserPassword(id: string): Promise<void> {
  return api(`/users/${id}/reset-password`, { method: 'POST' })
}
```

`frontend/src/api/profileApi.ts`: delete `username: string` from `Profile`.

- [ ] **Step 2: UserForm** — remove the `username` state/field and the `password` state/field entirely; body becomes `{ email, name, roles, division_id: divisionId || null, ...(user ? { active } : {}) }`. In place of the old temporary-password block, show for new users only:

```tsx
      {!user && (
        <p className="max-w-lg text-sm text-muted">
          New accounts start with the default password <span className="font-medium">Welcome@1</span> and
          must choose their own the first time they sign in.
        </p>
      )}
```

- [ ] **Step 3: UsersPage** — drop the `Username` `<th>` and the `{u.username}` `<td>` (Name/Email lead the table).

- [ ] **Step 4: UserEditPage** — heading `Edit user: {user.name}`; delete-confirm uses `user.email`. Replace the whole reset section (drop `newPassword` state and the `Input` import if now unused):

```tsx
  const [resetMsg, setResetMsg] = useState<string | null>(null)
  const resetMutation = useMutation({
    mutationFn: () => resetUserPassword(id),
    onSuccess: () => setResetMsg('Password reset to the default. The user must choose a new one at next sign-in.'),
  })
  ...
      <div className="max-w-lg border-t border-border pt-6">
        <h2 className="mb-1 font-semibold text-fg">Reset password</h2>
        <p className="mb-2 text-sm text-muted">
          Sets the account back to the default password (Welcome@1); the user must choose
          their own at next sign-in.
        </p>
        <Button disabled={resetMutation.isPending}
          onClick={() => {
            if (window.confirm(`Reset ${user.email} to the default password?`)) resetMutation.mutate()
          }}>Reset to default password</Button>
        {resetMsg && <p className="mt-2 text-sm text-emerald-600 dark:text-emerald-400">{resetMsg}</p>}
      </div>
```

- [ ] **Step 5: Approver labels** — `DivisionForm.tsx:40` and `ThresholdsPage.tsx:61`: `` `${u.name} (${u.username})` `` → `` `${u.name} (${u.email})` ``.

- [ ] **Step 6: Typecheck + tests + build**

Run (from `frontend/`): `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json && node ./node_modules/vitest/vitest.mjs run && node ./node_modules/vite/bin/vite.js build`
Expected: clean. `grep -rn username frontend/src` returns nothing.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(web): admin user screens keyed on email; reset-to-default password"
```

---

### Task 9: End-to-end verification + docs

**Files:**
- Modify: `CLAUDE.md`
- Verify: whole app

**Interfaces:** none — verification and documentation.

- [ ] **Step 1: Full test pass**

Run: `cd backend && pytest -q` then from `frontend/`: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json && node ./node_modules/vitest/vitest.mjs run && node ./node_modules/vite/bin/vite.js build`
Expected: everything green.

- [ ] **Step 2: Smoke the real app** (use the project `verify` skill if running interactively). Reseed dev db (`cd backend && flask db upgrade && python seed.py`), start via `run-app.ps1`, then: sign in as `admin@uniteduptime.com` / `ChangeMe123!` (no forced change); create a user from Admin → Users (note the default-password hint, no password field); sign out; sign in as the new user with `Welcome@1` → forced to the Set-your-new-password screen (deep links/API blocked); set a password → lands on dashboard; admin "Reset to default password" re-flags them.

- [ ] **Step 3: Update CLAUDE.md** — (a) dev login line becomes `Dev login: **admin@uniteduptime.com / ChangeMe123!**`; (b) in the backend layout section, note `auth` handles email-based login and `set-password`, and that `must_change_password` gates the API via an app-level `before_request` (403 `PASSWORD_CHANGE_REQUIRED`); (c) in the Data model User bullet, replace `username` with `must_change_password`; (d) frontend section: add `ChangePasswordPage` to the routes list; (e) Roles section or Conventions: one line — new users/admin resets start at `DEFAULT_PASSWORD` (`Welcome@1`).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: email-based login, default password + forced change"
```
