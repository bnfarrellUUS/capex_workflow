# CAPRI Entra ID SSO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Microsoft Entra ID single sign-on to CAPRI, shipped with the feature flag unset so nothing changes for users until IT delivers an app registration.

**Architecture:** A new `app/services/sso_service.py` holds every SSO decision as pure functions over claim dicts and `User` rows, and is the only module importing `msal`. Three thin routes on the existing `app/blueprints/auth.py` drive it, and `POST /api/auth/login` gains a 403 as its first line when SSO is configured. The React login screen becomes tri-state (loading / Microsoft button only / password form).

**Tech Stack:** Flask 3, SQLAlchemy 2.0 typed `Mapped`, Alembic, Flask-Login, `msal` (new), Pydantic v2, pytest; React 19 + TypeScript, TanStack Query 5, React Router 7, vitest.

**Spec:** `docs/superpowers/specs/2026-09-21-capri-entra-sso-design.md`

## Global Constraints

- **Do not enable SSO.** `CAPRI_ENABLE_SSO` ships unset. This plan is Step 0 of the guide's §10 rollout.
- **Env var prefix is `CAPRI_`**, exactly: `CAPRI_ENABLE_SSO`, `CAPRI_SSO_TENANT_ID`, `CAPRI_SSO_CLIENT_ID`, `CAPRI_SSO_CLIENT_SECRET`, `CAPRI_SSO_ALLOWED_GROUPS`, `CAPRI_SSO_REDIRECT_URI`.
- **`msal>=1.20`** in `backend/requirements.txt`.
- **Error codes are a fixed vocabulary**, never interpolated text: `no_groups_claim`, `not_in_group`, `unknown_user`, `inactive_user`, `identity_mismatch`, `auth_failed`. No exception message, claim value or email address may reach the browser.
- **Failures redirect to `/login?sso_error=<code>`** — never `/`, and never a JSON body.
- **`sso_config()` reads `os.environ` at call time.** Never a `Config` class attribute; `app/config.py` assigns at import, which would make the config untestable.
- **`response_mode` stays at MSAL's default (query/GET).** `SESSION_COOKIE_SAMESITE="Lax"` would starve a `form_post` callback of its session cookie.
- **SSO sessions use `remember=False`**; the password path keeps `remember=True`.
- **Scopes are `[]`.** CAPRI calls nothing on the user's behalf.
- **Windows/`&`-in-path:** run frontend tooling through node — `node ./node_modules/vitest/vitest.mjs run`, `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`, `node ./node_modules/vite/bin/vite.js build`. Never `npm run ...` from a tool that shells out.
- **Backend commands** run from `backend/` with its venv: `.venv/Scripts/python.exe -m pytest -q`.
- **Push after each commit:** `git push origin main && git push azure main:dev`. **Never** push to `azure main`.
- Frontend test files need `// @vitest-environment jsdom` on line 1 — the vitest default environment is `node`.

---

### Task 1: Fix `users.reset_token` so Azure SQL can hold more than one user

This is a **pre-existing bug and a prerequisite**, not part of SSO. `reset_token` is `unique=True, nullable=True`. SQL Server treats NULLs as equal in a UNIQUE index and permits exactly one, so CAPRI currently cannot hold a second user on Azure SQL. Gate 3 of SSO requires every user to have a row, so this must be fixed first. It gets its own revision and its own commit.

**Files:**
- Create: `backend/migrations/versions/b8c9d0e1f2a3_reset_token_filtered_unique.py`
- Modify: `backend/app/models/__init__.py:78` (comment only)
- Test: verified against the live Azure SQL dev server (see Step 4) — a SQLite-only unit test cannot exercise the SQL Server branch

**Interfaces:**
- Consumes: nothing.
- Produces: Alembic revision `b8c9d0e1f2a3`, whose `down_revision` is `e7f8a9b0c1d2`. Task 2's revision revises `b8c9d0e1f2a3`.

- [ ] **Step 1: Confirm the bug still reproduces**

From `backend/`, write `../tmp_check.py` and run it with the venv python:

```python
import os, sys
sys.path.insert(0, os.getcwd())
from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    with db.engine.connect() as c:
        t = c.begin()
        try:
            c.execute(text("""insert into users
              (id,email,name,password_hash,roles,active,must_change_password,failed_logins,created_at,updated_at)
              values ('zzt1','nulltest1@example.com','NullTest1','x','[]',1,0,0,SYSUTCDATETIME(),SYSUTCDATETIME())"""))
            print("INSERT OK - bug is already fixed or dialect is not SQL Server")
        except Exception as e:
            print("REPRODUCED:", type(e).__name__, str(e)[:200])
        finally:
            t.rollback()
```

Run: `.venv/Scripts/python.exe ../tmp_check.py`
Expected: `REPRODUCED: IntegrityError ... Violation of UNIQUE KEY constraint 'UQ__users__...'. The duplicate key value is (<NULL>)`

If it prints `INSERT OK`, `AZURE_SQL_ODBC` is commented out in `backend/.env` and you are on SQLite. Uncomment it, or this task cannot be verified.

- [ ] **Step 2: Write the migration**

Create `backend/migrations/versions/b8c9d0e1f2a3_reset_token_filtered_unique.py`:

```python
"""users.reset_token: filtered unique index on SQL Server

SQL Server treats NULLs as equal in a UNIQUE index and allows exactly one, so
the plain UNIQUE constraint on this nullable column capped the table at ONE
user with no reset token -- i.e. one user, full stop. A filtered unique index
is the standard SQL Server idiom for a nullable-unique column.

SQLite needs no change: it treats NULLs as distinct in a UNIQUE index, so many
users with no reset token are already legal there. The two dialects therefore
converge on the same behaviour rather than the same DDL.

Revision ID: b8c9d0e1f2a3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa


revision = 'b8c9d0e1f2a3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None

INDEX_NAME = 'uq_users_reset_token'


def _unique_constraint_on(bind, table, column):
    """Name of the UNIQUE constraint covering table.column, or None.

    SQL Server auto-generates the name (UQ__users__25F405EB36267CDA on the dev
    server) and it differs per database, so it must be looked up rather than
    assumed -- the same failure f3ed810 fixed for a foreign key.
    """
    return bind.execute(sa.text(
        "SELECT kc.name FROM sys.key_constraints kc "
        "JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id "
        "AND ic.index_id = kc.unique_index_id "
        "JOIN sys.columns c ON c.object_id = kc.parent_object_id "
        "AND c.column_id = ic.column_id "
        "WHERE kc.parent_object_id = OBJECT_ID(:table) AND kc.type = 'UQ' "
        "AND c.name = :column"
    ), {"table": table, "column": column}).scalar()


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        return
    name = _unique_constraint_on(bind, 'users', 'reset_token')
    if name:
        op.drop_constraint(name, 'users', type_='unique')
    op.create_index(INDEX_NAME, 'users', ['reset_token'], unique=True,
                    mssql_where=sa.text('reset_token IS NOT NULL'))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        return
    op.drop_index(INDEX_NAME, table_name='users')
    op.create_unique_constraint(INDEX_NAME, 'users', ['reset_token'])
```

- [ ] **Step 3: Note the divergence on the model**

In `backend/app/models/__init__.py`, the `reset_token` line keeps `unique=True` (correct on SQLite, which is what `create_all` builds in tests). Add the comment above it so nobody "fixes" it back:

```python
    # unique=True is correct on SQLite, which treats NULLs as distinct. SQL
    # Server does not, so migration b8c9d0e1f2a3 replaces the constraint there
    # with a unique index filtered to `reset_token IS NOT NULL`. Without that,
    # the table can hold only ONE row with a NULL reset_token.
    reset_token: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
```

- [ ] **Step 4: Run the migration against Azure SQL and prove the fix**

Run: `.venv/Scripts/python.exe -m flask db upgrade`
Expected: upgrades to `b8c9d0e1f2a3` with no error.

Then re-run the Step 1 script: `.venv/Scripts/python.exe ../tmp_check.py`
Expected: `INSERT OK` — a second user with a NULL `reset_token` now inserts.

Then confirm the index is filtered:

```python
# append to ../tmp_check.py, or run separately
with app.app_context():
    with db.engine.connect() as c:
        for r in c.execute(text(
            "select i.name, i.is_unique, i.has_filter, i.filter_definition "
            "from sys.indexes i where i.object_id=object_id('users') and i.name='uq_users_reset_token'")):
            print(r)
```
Expected: one row with `is_unique=True`, `has_filter=True`, filter `([reset_token] IS NOT NULL)`.

- [ ] **Step 5: Confirm the SQLite path and the suite are unaffected**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 336 passed (the existing count; no new tests yet).

Then check a fresh SQLite database still reaches head. Temporarily comment `AZURE_SQL_ODBC` in `backend/.env`, then:

Run: `.venv/Scripts/python.exe -m flask db upgrade`
Expected: reaches `b8c9d0e1f2a3`, no error (the sqlite branch returns immediately).

Uncomment `AZURE_SQL_ODBC` again. Delete `../tmp_check.py`.

- [ ] **Step 6: Commit and push**

```bash
git add backend/migrations/versions/b8c9d0e1f2a3_reset_token_filtered_unique.py backend/app/models/__init__.py
git commit -m "fix(db): filtered unique index for users.reset_token on SQL Server

A plain UNIQUE constraint on a nullable column allows exactly one NULL in SQL
Server, so CAPRI could hold only one user with no reset token -- one user in
total -- on Azure SQL. Inserting a second failed with 'duplicate key value is
(<NULL>)'. SQLite treats NULLs as distinct, which is why dev never saw it.

Replaces the constraint with a unique index filtered to reset_token IS NOT
NULL. The constraint name is auto-generated and differs per database, so it is
looked up in sys.key_constraints rather than assumed, as f3ed810 did for a
foreign key. SQLite needs no change and its branch returns immediately.

Found while designing Entra SSO, whose user-row gate needs a row per user.

Verified: flask db upgrade to b8c9d0e1f2a3 on the Azure SQL dev server, after
which a second user with a NULL reset_token inserts and the index reports
has_filter=1; a fresh SQLite file also reaches head; backend suite 336 passed.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

### Task 2: Add `users.entra_oid`

The column gate 4 compares against. Nullable and **not unique** — gate 4 finds the row by email then compares, so uniqueness buys nothing, and a nullable-unique column on SQL Server is exactly the trap Task 1 just fixed.

**Files:**
- Modify: `backend/app/models/__init__.py` (User, after `reset_token_expiry`)
- Create: `backend/migrations/versions/c9d0e1f2a3b4_users_entra_oid.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: revision `b8c9d0e1f2a3` from Task 1.
- Produces: `User.entra_oid: Mapped[Optional[str]]`, `String(36)`, nullable, default `None`. Task 5's `resolve_user` reads and writes it. Alembic revision `c9d0e1f2a3b4`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_models.py`:

```python
def test_user_entra_oid_defaults_to_none(app):
    from app.extensions import db
    from app.models import User
    from app.services.security import hash_password

    u = User(email="oid@x.com", name="Oid", password_hash=hash_password("secret123"))
    db.session.add(u)
    db.session.commit()
    # Nullable and unset for every pre-SSO row; sso_service pins it on first
    # SSO sign-in.
    assert u.entra_oid is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_models.py::test_user_entra_oid_defaults_to_none -v`
Expected: FAIL — `TypeError: 'entra_oid' is an invalid keyword argument` or `AttributeError: 'User' object has no attribute 'entra_oid'`

- [ ] **Step 3: Add the column to the model**

In `backend/app/models/__init__.py`, inside `class User`, immediately after the `reset_token_expiry` line:

```python
    # The Entra ID object ID, pinned on this user's first SSO sign-in and
    # compared on every one after (sso_service gate 4). NOT unique: the row is
    # found by email and this only confirms it is the same person, and a
    # nullable-unique column caps the table at one NULL on SQL Server (see
    # migration b8c9d0e1f2a3).
    entra_oid: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_models.py::test_user_entra_oid_defaults_to_none -v`
Expected: PASS

- [ ] **Step 5: Write the migration**

Create `backend/migrations/versions/c9d0e1f2a3b4_users_entra_oid.py`:

```python
"""add users.entra_oid

Pinned on a user's first SSO sign-in and compared on every one after, so a
recycled or reassigned email address cannot inherit an existing user's roles,
division scope and authorship of approval-history rows.

Nullable, and deliberately NOT unique: the row is located by email and this
column only confirms it is the same person. See b8c9d0e1f2a3 for why a
nullable-unique column is a trap on SQL Server.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-21

"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('entra_oid', sa.String(length=36), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('entra_oid')
```

- [ ] **Step 6: Run the migration on both dialects**

With `AZURE_SQL_ODBC` active in `backend/.env`:
Run: `.venv/Scripts/python.exe -m flask db upgrade`
Expected: upgrades to `c9d0e1f2a3b4`.

Verify the column landed and existing rows are NULL:

Run: `.venv/Scripts/python.exe -c "import os,sys; sys.path.insert(0,os.getcwd()); from app import create_app; from app.extensions import db; from sqlalchemy import text; app=create_app(); ctx=app.app_context(); ctx.push(); print(db.session.execute(text('select count(*) total, count(entra_oid) pinned from users')).one())"`
Expected: `pinned` is 0 — every pre-existing row is NULL.

Then comment `AZURE_SQL_ODBC` out, run `flask db upgrade` against SQLite, confirm it reaches `c9d0e1f2a3b4`, and uncomment it again.

- [ ] **Step 7: Run the suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 337 passed

- [ ] **Step 8: Commit and push**

```bash
git add backend/app/models/__init__.py backend/migrations/versions/c9d0e1f2a3b4_users_entra_oid.py backend/tests/test_models.py
git commit -m "feat(sso): add users.entra_oid

The column SSO gate 4 compares against: pinned on a user's first SSO sign-in,
checked on every one after, so a recycled or reassigned email cannot inherit an
existing user's roles, division scope and authorship of approval-history rows.

Nullable and deliberately not unique -- the row is found by email and this only
confirms the person, and a nullable-unique column caps the table at one NULL on
SQL Server (b8c9d0e1f2a3).

Verified: flask db upgrade to c9d0e1f2a3b4 on Azure SQL with every existing row
NULL, and on a fresh SQLite file; backend suite 337 passed.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

### Task 3: `sso_service` config, error vocabulary and the redirect guard

The parts with no MSAL involvement, plus the conftest fixture that stops a developer's `.env` from poisoning the suite. Do this before anything that touches MSAL.

**Files:**
- Create: `backend/app/services/sso_service.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_sso.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ERROR_CODES: tuple[str, ...]` — the six codes.
  - `SsoError(code: str, detail: str = "")` with attribute `.code`.
  - `sso_config() -> dict | None` with keys `tenant`, `client_id`, `client_secret`, `groups` (a `set[str]`), `redirect_uri`.
  - `safe_next_path(value: str | None) -> str`.
  - `SCOPES: list[str]` (empty).
  - pytest fixture `_no_ambient_sso` (autouse) and helper `sso_env(monkeypatch, **overrides)` in `tests/test_sso.py`.

- [ ] **Step 1: Add `msal` and install it**

In `backend/requirements.txt`, after the `Flask-WTF` line:

```
msal>=1.20  # Entra ID SSO (authorization-code flow, ID token validation)
```

Run: `.venv/Scripts/python.exe -m pip install -r requirements.txt`
Expected: `msal` installs successfully.

- [ ] **Step 2: Add the ambient-`.env` guard to conftest**

`app/config.py` calls `load_dotenv()` at import, and `conftest.py` imports `create_app` at module scope — so by the time any fixture runs, a developer's `CAPRI_ENABLE_SSO=1` is already in `os.environ` and would 403 every password-login test. Which tests fail would shift as tests were added, because it depends on import order.

Add to `backend/tests/conftest.py`, above the existing `app` fixture:

```python
import os

SSO_ENV_VARS = ("CAPRI_ENABLE_SSO", "CAPRI_SSO_TENANT_ID", "CAPRI_SSO_CLIENT_ID",
                "CAPRI_SSO_CLIENT_SECRET", "CAPRI_SSO_ALLOWED_GROUPS",
                "CAPRI_SSO_REDIRECT_URI")


@pytest.fixture(autouse=True)
def _no_ambient_sso():
    """Keep a developer's .env out of the suite.

    app/config.py calls load_dotenv() at import and this module imports
    create_app at module scope, so CAPRI_ENABLE_SSO=1 in a local .env would
    otherwise 403 every password-login test -- and *which* tests failed would
    move around as tests were added, because it depends on import order. SSO
    tests opt back in with monkeypatch.
    """
    saved = {k: os.environ.pop(k, None) for k in SSO_ENV_VARS}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
```

- [ ] **Step 3: Write the failing tests**

Create `backend/tests/test_sso.py`:

```python
import pytest

from app.services import sso_service


def sso_env(monkeypatch, **overrides):
    """Put a complete, valid SSO config in the environment.

    Pass a keyword as None to remove that variable, which is how the
    fail-closed cases below drop one value at a time.
    """
    values = {
        "CAPRI_ENABLE_SSO": "1",
        "CAPRI_SSO_TENANT_ID": "tenant-guid",
        "CAPRI_SSO_CLIENT_ID": "client-guid",
        "CAPRI_SSO_CLIENT_SECRET": "shh",
        "CAPRI_SSO_ALLOWED_GROUPS": "group-a,group-b",
        "CAPRI_SSO_REDIRECT_URI": "http://localhost:5100/api/auth/sso/callback",
    }
    values.update(overrides)
    for key, value in values.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_config_is_none_without_the_flag(monkeypatch):
    sso_env(monkeypatch, CAPRI_ENABLE_SSO=None)
    assert sso_service.sso_config() is None


def test_config_is_none_when_the_flag_is_not_exactly_one(monkeypatch):
    sso_env(monkeypatch, CAPRI_ENABLE_SSO="true")
    assert sso_service.sso_config() is None


def test_config_is_complete_when_every_value_is_present(monkeypatch):
    sso_env(monkeypatch)
    cfg = sso_service.sso_config()
    assert cfg["tenant"] == "tenant-guid"
    assert cfg["client_id"] == "client-guid"
    assert cfg["client_secret"] == "shh"
    assert cfg["redirect_uri"] == "http://localhost:5100/api/auth/sso/callback"
    # Comma-separated object IDs become a set for the gate-2 intersection.
    assert cfg["groups"] == {"group-a", "group-b"}


@pytest.mark.parametrize("missing", [
    "CAPRI_SSO_TENANT_ID",
    "CAPRI_SSO_CLIENT_ID",
    "CAPRI_SSO_CLIENT_SECRET",
    "CAPRI_SSO_ALLOWED_GROUPS",
    "CAPRI_SSO_REDIRECT_URI",
])
def test_config_fails_closed_when_any_value_is_missing(monkeypatch, missing):
    # Fail closed on configuration: an incomplete config behaves as SSO-off so
    # a deployment typo cannot lock every user out of a working app.
    sso_env(monkeypatch, **{missing: None})
    assert sso_service.sso_config() is None


def test_config_fails_closed_on_a_blank_group_list(monkeypatch):
    # An empty group list would make gate 2 intersect against nothing.
    sso_env(monkeypatch, CAPRI_SSO_ALLOWED_GROUPS=" , ")
    assert sso_service.sso_config() is None


def test_error_codes_are_the_agreed_vocabulary():
    assert set(sso_service.ERROR_CODES) == {
        "no_groups_claim", "not_in_group", "unknown_user",
        "inactive_user", "identity_mismatch", "auth_failed",
    }


def test_sso_error_rejects_an_unknown_code():
    with pytest.raises(AssertionError):
        sso_service.SsoError("made_up_code")


def test_sso_error_keeps_detail_off_the_code():
    err = sso_service.SsoError("auth_failed", "tenant said no")
    assert err.code == "auth_failed"
    assert "tenant said no" in str(err)


@pytest.mark.parametrize("value", [
    "/requests/42",
    "/a/b?c=d",
    "/",
])
def test_safe_next_path_accepts_same_origin_paths(value):
    assert sso_service.safe_next_path(value) == value


@pytest.mark.parametrize("value", [
    "//evil.com",              # protocol-relative: another host entirely
    "https://evil.com",        # absolute
    "http://evil.com",
    "/ok\\evil",               # some browsers normalise the backslash to /
    "/ok\revil",               # header injection
    "/ok\nevil",
    "requests/42",             # not absolute
    "",
    None,
])
def test_safe_next_path_rejects_everything_else(value):
    # /sso/login is reachable before anyone signs in, so an unchecked next=
    # would make our own login endpoint an open redirect -- a phishing link
    # that genuinely starts at our hostname.
    assert sso_service.safe_next_path(value) == ""
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sso.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.sso_service'`

- [ ] **Step 5: Write the module**

Create `backend/app/services/sso_service.py`:

```python
"""Entra ID SSO -- spec docs/superpowers/specs/2026-09-21-capri-entra-sso-design.md.

The ONLY module in CAPRI that imports msal. Everything above it deals in claim
dicts and User rows, which is what makes the callback's six refusal codes
testable without a network.

WHAT THIS MODULE DELIBERATELY DOES NOT DO:
  - It never validates a token by hand. acquire_token_by_auth_code_flow checks
    the signature against the tenant's JWKS, the issuer, the audience, the
    nonce and the state. Reimplementing any of that is how signature checks get
    accidentally disabled.
  - It keeps no token cache and asks for no refresh token. CAPRI acts on
    nothing on a user's behalf, so the access token is discarded the moment the
    claims are read. Only the Flask-Login session survives.
"""
import os

import msal

from app.extensions import db
from app.models import User

# The complete set of refusal codes. They reach the browser in a query string,
# so they are a fixed server-side vocabulary and never interpolated text: no
# exception message, claim value or email address may leak this way.
ERROR_CODES = (
    "no_groups_claim",
    "not_in_group",
    "unknown_user",
    "inactive_user",
    "identity_mismatch",
    "auth_failed",
)

# Only the OIDC basics. CAPRI calls no downstream API on the user's behalf, so
# a Graph scope would obtain an access token nothing uses -- and a token
# obtained is a token that can leak.
SCOPES = []


class SsoError(Exception):
    """A refusal carrying a code from ERROR_CODES."""

    def __init__(self, code, detail=""):
        assert code in ERROR_CODES, f"unknown SSO error code {code!r}"
        super().__init__(detail or code)
        self.code = code


def sso_config():
    """Entra settings from the environment, or None.

    None means SSO is off. Not-None means SSO is the *only* way in: password
    sign-in is refused and the login screen hides the email/password form. One
    condition, checked in both places -- two independent flags drift apart and
    eventually leave a door open nobody remembers.

    Fail closed on configuration: any missing value yields None, i.e. SSO-off,
    i.e. password login keeps working. That is deliberately the *safe* failure
    rather than the *secure* one -- an incomplete config is a deployment
    mistake, and refusing every login over a typo is worse. create_app logs a
    WARNING so the mistake is visible rather than silent.

    Read from os.environ at CALL time, never into module-level constants at
    import: it costs nothing, and it is what lets the suite flip the config per
    test with monkeypatch. app/config.py's import-time pattern must not be
    copied here.
    """
    if os.environ.get("CAPRI_ENABLE_SSO", "").strip() != "1":
        return None
    cfg = {
        "tenant": os.environ.get("CAPRI_SSO_TENANT_ID", "").strip(),
        "client_id": os.environ.get("CAPRI_SSO_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("CAPRI_SSO_CLIENT_SECRET", "").strip(),
        "groups": {g.strip() for g
                   in os.environ.get("CAPRI_SSO_ALLOWED_GROUPS", "").split(",")
                   if g.strip()},
        "redirect_uri": os.environ.get("CAPRI_SSO_REDIRECT_URI", "").strip(),
    }
    if not all((cfg["tenant"], cfg["client_id"], cfg["client_secret"],
                cfg["groups"], cfg["redirect_uri"])):
        return None
    return cfg


def safe_next_path(value):
    """A post-login landing path from an untrusted query string, or "".

    /api/auth/sso/login is reachable before anyone has signed in, so whatever
    it is handed has to be treated as hostile: only a path on this origin may
    come back out. A value starting "//" -- or carrying a backslash, which some
    browsers normalise to "/" -- would redirect to another host entirely,
    turning our own login endpoint into an open redirect. The link genuinely
    starts at our hostname, so it survives a careful look and lands on a login
    clone.
    """
    v = (value or "").strip()
    if not v.startswith("/") or v.startswith("//"):
        return ""
    if any(c in v for c in ("\\", "\r", "\n")):
        return ""
    return v
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sso.py -q`
Expected: PASS — 24 passed (parametrized cases count individually)

- [ ] **Step 7: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 361 passed (336 baseline + 1 from Task 2 + 24 here). If any pre-existing test now fails, the conftest fixture is wrong — do not proceed.

- [ ] **Step 8: Commit and push**

```bash
git add backend/app/services/sso_service.py backend/tests/test_sso.py backend/tests/conftest.py backend/requirements.txt
git commit -m "feat(sso): SSO config, error vocabulary and open-redirect guard

sso_config() reads the six CAPRI_SSO_* variables from os.environ at call time
and returns None unless the flag is 1 and every value is present, including at
least one group object ID. Not-None is the single switch that also means
password login is closed. Reading at call time rather than into config class
attributes is what lets the suite flip the config per test.

safe_next_path() allows only same-origin paths: /sso/login is reachable before
sign-in, so an unchecked next= would make our own login endpoint an open
redirect that starts at our real hostname.

SsoError carries a code from a fixed six-item vocabulary, asserted on
construction, because codes reach the browser in a query string -- no exception
text, claim value or email may leak that way.

conftest gains an autouse fixture clearing the SSO variables: config.py calls
load_dotenv() at import, so a developer's CAPRI_ENABLE_SSO=1 would otherwise
403 every password-login test, with the failures moving around as tests were
added.

Verified: 24 new tests pass; backend suite 361 passed.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

### Task 4: The MSAL seam — `_client`, `build_auth_flow`, `redeem`

**Files:**
- Modify: `backend/app/services/sso_service.py`
- Test: `backend/tests/test_sso.py`

**Interfaces:**
- Consumes: `sso_config()`, `SsoError`, `SCOPES` from Task 3.
- Produces:
  - `_client(cfg) -> msal.ConfidentialClientApplication` — the single seam tests monkeypatch.
  - `build_auth_flow(cfg) -> dict` — the flow dict with `auth_uri`, `state`, and the PKCE verifier.
  - `redeem(cfg, flow: dict, args) -> dict` — validated `id_token_claims`, or raises `SsoError("auth_failed")`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_sso.py`:

```python
class FakeMsalApp:
    """Stands in for msal.ConfidentialClientApplication.

    Monkeypatching sso_service._client to return one of these is the only fake
    in the SSO tests -- everything else runs for real. We are testing our
    gates, not Microsoft's protocol.
    """

    def __init__(self, flow=None, result=None, raises=None):
        self._flow = flow if flow is not None else {
            "auth_uri": "https://login.microsoftonline.com/tenant-guid/authorize?x=1",
            "state": "st",
        }
        self._result = result
        self._raises = raises
        self.initiate_calls = []
        self.acquire_calls = []

    def initiate_auth_code_flow(self, scopes, redirect_uri=None):
        self.initiate_calls.append((scopes, redirect_uri))
        if self._raises:
            raise self._raises
        return self._flow

    def acquire_token_by_auth_code_flow(self, flow, args):
        self.acquire_calls.append((flow, args))
        if self._raises:
            raise self._raises
        return self._result


def use_fake(monkeypatch, fake):
    monkeypatch.setattr(sso_service, "_client", lambda cfg: fake)
    return fake


def test_build_auth_flow_asks_for_no_scopes(monkeypatch):
    sso_env(monkeypatch)
    fake = use_fake(monkeypatch, FakeMsalApp())
    flow = sso_service.build_auth_flow(sso_service.sso_config())
    assert flow["auth_uri"].startswith("https://login.microsoftonline.com/")
    scopes, redirect_uri = fake.initiate_calls[0]
    # No Graph scope: CAPRI acts on nothing on the user's behalf, so an access
    # token would be one nothing uses and something that can leak.
    assert scopes == []
    assert redirect_uri == "http://localhost:5100/api/auth/sso/callback"


def test_redeem_returns_id_token_claims(monkeypatch):
    sso_env(monkeypatch)
    claims = {"preferred_username": "A@X.com", "groups": ["group-a"], "oid": "oid-1"}
    use_fake(monkeypatch, FakeMsalApp(result={"id_token_claims": claims}))
    assert sso_service.redeem(sso_service.sso_config(), {"state": "st"}, {"code": "c"}) == claims


def test_redeem_collapses_an_msal_exception_to_auth_failed(monkeypatch):
    # MSAL raises a bare ValueError for a mismatched or absent state -- the
    # replay case this flow exists to catch -- and the same call also does
    # network I/O, which fails in its own ways. Every failure means the same
    # thing to a user, so it collapses to one code.
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(raises=ValueError("state mismatch")))
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.redeem(sso_service.sso_config(), {"state": "st"}, {"code": "c"})
    assert exc.value.code == "auth_failed"


def test_redeem_treats_an_error_result_as_auth_failed(monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(result={
        "error": "invalid_grant",
        "error_description": "AADSTS70008: expired",
    }))
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.redeem(sso_service.sso_config(), {"state": "st"}, {"code": "c"})
    assert exc.value.code == "auth_failed"
    # The description can quote back attacker-influenced input, so it is logged
    # via the detail, never returned to the browser.
    assert "AADSTS70008" in str(exc.value)


def test_redeem_rejects_a_result_with_no_claims(monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(result={"access_token": "no claims here"}))
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.redeem(sso_service.sso_config(), {"state": "st"}, {"code": "c"})
    assert exc.value.code == "auth_failed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sso.py -q -k "build_auth_flow or redeem"`
Expected: FAIL — `AttributeError: module 'app.services.sso_service' has no attribute 'build_auth_flow'`

- [ ] **Step 3: Implement the three functions**

Append to `backend/app/services/sso_service.py`:

```python
def _client(cfg):
    """A HOOK, and the one seam the tests fake.

    Everything else in this module and in blueprints/auth.py is exercised for
    real; monkeypatching this is what keeps the suite off the network.
    """
    return msal.ConfidentialClientApplication(
        cfg["client_id"],
        authority=f"https://login.microsoftonline.com/{cfg['tenant']}",
        client_credential=cfg["client_secret"],
    )


def build_auth_flow(cfg):
    """The flow dict carrying state, nonce and the PKCE code_verifier.

    The caller stores this in the Flask session and MUST pop it on the way
    back: a flow read in place rather than popped makes a replayed callback URL
    usable a second time.

    response_mode is left at MSAL's default (query, i.e. a GET redirect) and
    MUST NOT be changed to form_post. app/config.py sets
    SESSION_COOKIE_SAMESITE="Lax", which does not send the cookie on a
    cross-site POST -- so a form_post callback would arrive with no session,
    the flow dict would be unreachable, and every sign-in would fail while
    looking exactly like an Entra misconfiguration.
    """
    return _client(cfg).initiate_auth_code_flow(
        SCOPES, redirect_uri=cfg["redirect_uri"])


def redeem(cfg, flow, args):
    """Exchange the code for validated ID token claims.

    `args` is request.args; MSAL reads `code` and `state` from it and compares
    the state against the flow dict. A mismatched or absent state -- the
    CSRF/replay case this flow exists to catch -- does NOT come back as an
    error dict: MSAL raises a bare ValueError, which is why the call below is
    wrapped rather than trusted to always return.
    """
    try:
        result = _client(cfg).acquire_token_by_auth_code_flow(flow, dict(args))
    except Exception as e:
        # Deliberately broad, not `except ValueError`. MSAL documents
        # client-side data errors as ValueError, but this call also does
        # network I/O, which fails in its own ways. Every failure means the
        # same thing to a user -- sign-in did not complete -- so it collapses
        # to one code rather than leaking which exception type fired.
        raise SsoError("auth_failed", f"exception during token exchange: {e}") from e
    if "error" in result or "id_token_claims" not in result:
        # The description can quote back attacker-influenced input, so it goes
        # in the detail (logged) and never in the code (returned).
        raise SsoError(
            "auth_failed",
            str(result.get("error_description") or result.get("error")))
    return result["id_token_claims"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sso.py -q`
Expected: PASS — 29 passed in test_sso.py (24 + 5 new)

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/services/sso_service.py backend/tests/test_sso.py
git commit -m "feat(sso): MSAL auth-code flow (build_auth_flow, redeem)

_client is the single seam the tests fake, so every other line of the SSO path
runs for real. build_auth_flow asks for no scopes -- CAPRI calls nothing on the
user's behalf, so an access token would be one nothing uses.

response_mode stays at MSAL's default query/GET. SESSION_COOKIE_SAMESITE=Lax
does not send the cookie on a cross-site POST, so a form_post callback would
arrive with no session, make the flow dict unreachable, and fail every sign-in
while looking exactly like an Entra misconfiguration.

redeem wraps the exchange in a broad except because MSAL raises a bare
ValueError for a mismatched state -- the replay case -- rather than returning
an error dict, and the same call also does network I/O. Every failure collapses
to auth_failed; the provider's description is logged, never returned, since it
can quote back attacker-influenced input.

Verified: 29 tests in test_sso.py pass.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

### Task 5: `resolve_user` — the four gates

**Files:**
- Modify: `backend/app/services/sso_service.py`
- Test: `backend/tests/test_sso.py`

**Interfaces:**
- Consumes: `SsoError` from Task 3; `User.entra_oid` from Task 2.
- Produces: `resolve_user(cfg, claims: dict) -> User`, raising `SsoError` with one of `no_groups_claim`, `not_in_group`, `unknown_user`, `inactive_user`, `identity_mismatch`. Task 6's callback calls it.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_sso.py`:

```python
def _sso_user(email="a@x.com", active=True, entra_oid=None):
    from app.extensions import db
    from app.models import User
    from app.services.security import hash_password

    u = User(email=email, name="A User", password_hash=hash_password("secret123"),
             roles='["REQUESTOR"]', active=active, entra_oid=entra_oid)
    db.session.add(u)
    db.session.commit()
    return u


def _claims(**over):
    c = {"preferred_username": "a@x.com", "groups": ["group-a"], "oid": "oid-1"}
    c.update(over)
    return c


def _cfg(monkeypatch):
    sso_env(monkeypatch)
    return sso_service.sso_config()


def test_gate1_absent_groups_claim_is_not_membership_of_nothing(app, monkeypatch):
    # Entra omits `groups` entirely and emits _claim_names once a user is in
    # enough groups, so an absent claim is indistinguishable from an empty one.
    # Treating it as a pass would silently disable this gate for exactly the
    # accounts most likely to be over-privileged. IT fixes this.
    _sso_user()
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(groups=None))
    assert exc.value.code == "no_groups_claim"


def test_gate1_rejects_a_non_list_groups_claim(app, monkeypatch):
    _sso_user()
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(groups="group-a"))
    assert exc.value.code == "no_groups_claim"


def test_gate2_rejects_a_non_member(app, monkeypatch):
    _sso_user()
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(groups=["some-other-group"]))
    assert exc.value.code == "not_in_group"


def test_gate2_accepts_membership_of_any_one_allowed_group(app, monkeypatch):
    u = _sso_user()
    got = sso_service.resolve_user(_cfg(monkeypatch), _claims(groups=["group-b"]))
    assert got.id == u.id


def test_gate3_rejects_an_unknown_email(app, monkeypatch):
    # Deliberately not auto-provisioned: a row is an admin's decision.
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(preferred_username="nobody@x.com"))
    assert exc.value.code == "unknown_user"


def test_gate3_rejects_an_inactive_user(app, monkeypatch):
    _sso_user(active=False)
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims())
    assert exc.value.code == "inactive_user"


def test_gate3_lowercases_the_email(app, monkeypatch):
    u = _sso_user(email="a@x.com")
    got = sso_service.resolve_user(_cfg(monkeypatch), _claims(preferred_username="A@X.COM"))
    assert got.id == u.id


def test_gate3_falls_back_to_the_email_claim(app, monkeypatch):
    # Which of preferred_username/email Entra populates depends on how the
    # account was created, so reading only the first refuses a real subset of
    # accounts as unknown.
    u = _sso_user()
    got = sso_service.resolve_user(
        _cfg(monkeypatch), _claims(preferred_username=None, email="a@x.com"))
    assert got.id == u.id


def test_gate4_pins_entra_oid_on_first_sight(app, monkeypatch):
    u = _sso_user(entra_oid=None)
    sso_service.resolve_user(_cfg(monkeypatch), _claims(oid="oid-1"))
    from app.extensions import db
    db.session.refresh(u)
    assert u.entra_oid == "oid-1"


def test_gate4_accepts_a_matching_oid(app, monkeypatch):
    u = _sso_user(entra_oid="oid-1")
    got = sso_service.resolve_user(_cfg(monkeypatch), _claims(oid="oid-1"))
    assert got.id == u.id


def test_gate4_refuses_a_different_oid_for_the_same_email(app, monkeypatch):
    # The email matched but the person did not. Refuse rather than hand over a
    # role, a division scope and authorship of approval-history rows.
    _sso_user(entra_oid="oid-1")
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(oid="oid-2"))
    assert exc.value.code == "identity_mismatch"


def test_gates_run_in_order_so_each_code_names_its_own_fixer(app, monkeypatch):
    # An inactive user who is also not in the group must report the GROUP
    # problem (IT) rather than the account problem (app admin): running the
    # gates out of order hands an IT problem to the wrong person.
    _sso_user(active=False)
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(groups=["nope"]))
    assert exc.value.code == "not_in_group"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sso.py -q -k "gate"`
Expected: FAIL — `AttributeError: module 'app.services.sso_service' has no attribute 'resolve_user'`

- [ ] **Step 3: Implement `resolve_user`**

Append to `backend/app/services/sso_service.py`:

```python
def resolve_user(cfg, claims):
    """Claims -> the User row that may sign in, or SsoError.

    Entra proves WHO. This function is the whole of what decides WHETHER, and
    the User row an admin created decides everything after: roles, division,
    delegate and approval routing are untouched by SSO.

    FOUR GATES, IN THIS ORDER, and the order is the guide's rather than the
    obvious one. Each gate's code names a different person to act on it, so
    running them out of order would hand an IT problem to an app admin.
    """
    # GATE 1 -- did the claim arrive at all?
    #
    # `None` is NOT "member of nothing". Entra omits `groups` entirely and
    # emits `_claim_names` instead once a user is in enough groups, so an
    # absent claim is indistinguishable from an empty one -- and treating it as
    # a pass would silently disable this gate for exactly the accounts most
    # likely to be over-privileged. IT fixes this, by setting Token
    # configuration to "Groups assigned to the application".
    groups = claims.get("groups")
    if not isinstance(groups, list):
        raise SsoError("no_groups_claim")

    # GATE 2 -- is this user in an authorizing group? An access request, not a
    # configuration bug. cfg["groups"] is never empty: sso_config() treats a
    # blank group list as unconfigured.
    if not set(groups) & cfg["groups"]:
        raise SsoError("not_in_group")

    # GATE 3 -- is there an active row an admin created?
    #
    # `email` is a fallback for `preferred_username`, not a nicety: which of
    # the two Entra populates depends on how the account was created, so
    # reading only the first refuses a real subset of accounts as unknown.
    email = (claims.get("preferred_username")
             or claims.get("email") or "").strip().lower()
    user = (db.session.query(User).filter_by(email=email).one_or_none()
            if email else None)
    if user is None:
        # Deliberately not auto-provisioned. A row is an admin's decision, and
        # access to the app is a different question from authority inside it.
        raise SsoError("unknown_user")
    if not user.active:
        raise SsoError("inactive_user")

    # GATE 4 -- is it the same person the row was pinned to?
    oid = (claims.get("oid") or "").strip()
    if user.entra_oid and user.entra_oid != oid:
        # The email matched but the person did not.
        raise SsoError("identity_mismatch")
    if not user.entra_oid and oid:
        user.entra_oid = oid
        db.session.commit()
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sso.py -q`
Expected: PASS — 41 passed in test_sso.py (29 + 12 new)

- [ ] **Step 5: Commit and push**

```bash
git add backend/app/services/sso_service.py backend/tests/test_sso.py
git commit -m "feat(sso): the four authorization gates

Entra proves who; resolve_user is the whole of what decides whether. Roles,
division, delegate and approval routing come from the User row exactly as they
do today -- there is no group-to-role mapping and no auto-provisioning, because
access to the app and authority inside it have different owners.

Gate order is load-bearing: each code names a different person to fix it, so an
inactive non-member reports not_in_group (IT) rather than inactive_user (app
admin). A test pins that.

Gate 1 rejects a non-list groups claim rather than treating it as membership of
nothing: Entra omits the claim and emits _claim_names once a user is in enough
groups, so an absent claim would silently disable the gate for exactly the
accounts most likely to be over-privileged.

Gate 3 lowercases the email and falls back from preferred_username to email,
since which one Entra populates depends on how the account was created.

Gate 4 pins entra_oid on first sight and refuses a later token whose oid
differs, so a recycled email cannot inherit a role, a division scope and
authorship of approval-history rows.

Verified: 41 tests in test_sso.py pass.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

### Task 6: The routes, the 403, and the startup warning

**Files:**
- Modify: `backend/app/blueprints/auth.py`
- Modify: `backend/app/__init__.py` (startup warning only; the `before_request` change is Task 7)
- Test: `backend/tests/test_sso_routes.py` (create)

**Interfaces:**
- Consumes: everything from `sso_service` (Tasks 3–5).
- Produces:
  - `GET /api/auth/config` → `{"ok": true, "sso_enabled": bool}`
  - `GET /api/auth/sso/login` → 302 to Entra, or 404 when SSO is off
  - `GET /api/auth/sso/callback` → 302 to `next` or `/login?sso_error=<code>`, or 404 when off
  - `POST /api/auth/login` → 403 when SSO is on
  - `_user_json` gains `"auth_method"`, `"sso"` or `"password"`. Task 8's frontend reads it.
  - `session["auth_method"]` is set by both login paths.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_sso_routes.py`:

```python
import pytest

from app.extensions import db
from app.models import User
from app.services import sso_service
from app.services.security import hash_password
from tests.test_sso import FakeMsalApp, sso_env, use_fake


def _user(email="a@x.com", active=True, entra_oid=None, must_change=False):
    u = User(email=email, name="A User", password_hash=hash_password("secret123"),
             roles='["REQUESTOR"]', active=active, entra_oid=entra_oid,
             must_change_password=must_change)
    db.session.add(u)
    db.session.commit()
    return u


def _claims(**over):
    c = {"preferred_username": "a@x.com", "groups": ["group-a"], "oid": "oid-1"}
    c.update(over)
    return c


# ---------- GET /api/auth/config ----------

def test_config_reports_sso_off_by_default(client):
    r = client.get("/api/auth/config")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True, "sso_enabled": False}


def test_config_reports_sso_on(client, monkeypatch):
    sso_env(monkeypatch)
    assert client.get("/api/auth/config").get_json()["sso_enabled"] is True


def test_config_needs_no_authentication(client, monkeypatch):
    # /api/auth/me 401s before login, so the login screen has no other way to
    # learn which form to draw.
    sso_env(monkeypatch)
    assert client.get("/api/auth/config").status_code == 200


# ---------- the routes do not exist when SSO is off ----------

@pytest.mark.parametrize("path", ["/api/auth/sso/login", "/api/auth/sso/callback"])
def test_sso_routes_404_when_sso_is_off(client, path):
    # 404, not 403: with the flag off these entry points do not exist.
    assert client.get(path).status_code == 404


# ---------- GET /api/auth/sso/login ----------

def test_sso_login_redirects_to_entra_and_stores_the_flow(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    r = client.get("/api/auth/sso/login")
    assert r.status_code == 302
    assert r.headers["Location"].startswith("https://login.microsoftonline.com/")
    with client.session_transaction() as sess:
        assert sess["sso_flow"]["state"] == "st"


def test_sso_login_stores_a_safe_next_path(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    client.get("/api/auth/sso/login?next=/requests/42")
    with client.session_transaction() as sess:
        assert sess["sso_next"] == "/requests/42"


def test_sso_login_discards_an_offsite_next_path(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    client.get("/api/auth/sso/login?next=//evil.com")
    with client.session_transaction() as sess:
        assert sess["sso_next"] == ""


def test_sso_login_redirects_rather_than_500s_on_an_msal_error(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(raises=RuntimeError("entra unreachable")))
    r = client.get("/api/auth/sso/login")
    assert r.status_code == 302
    assert r.headers["Location"] == "/login?sso_error=auth_failed"


# ---------- GET /api/auth/sso/callback ----------

def _start_flow(client, monkeypatch, claims=None, raises=None, next_path=None):
    """Drive /sso/login so a real flow is in the session, then fake the redeem."""
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    client.get(f"/api/auth/sso/login?next={next_path}" if next_path
               else "/api/auth/sso/login")
    use_fake(monkeypatch, FakeMsalApp(
        result=None if raises else {"id_token_claims": claims or _claims()},
        raises=raises))


def test_callback_signs_the_user_in(client, monkeypatch):
    _user()
    _start_flow(client, monkeypatch)
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.status_code == 302
    assert r.headers["Location"] == "/"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["auth_method"] == "sso"


def test_callback_sets_no_remember_cookie(client, monkeypatch):
    # Centralised revocation is much of the point of SSO: a 30-day remember
    # cookie would keep someone in CAPRI for weeks after Entra access was
    # withdrawn. The password path keeps its cookie.
    _user()
    _start_flow(client, monkeypatch)
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert not any(c.startswith("remember_token=")
                   for c in r.headers.getlist("Set-Cookie"))


def test_callback_honours_a_stored_deep_link(client, monkeypatch):
    _user()
    _start_flow(client, monkeypatch, next_path="/requests/42")
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/requests/42"


def test_callback_consumes_the_flow_so_a_replay_fails(client, monkeypatch):
    # A flow is single-use; leaving it in the session invites replay.
    _user()
    _start_flow(client, monkeypatch)
    assert client.get("/api/auth/sso/callback?code=c&state=st").status_code == 302
    client.post("/api/auth/logout")
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/login?sso_error=auth_failed"


def test_callback_with_no_flow_in_session_fails_closed(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(result={"id_token_claims": _claims()}))
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/login?sso_error=auth_failed"
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("claims_over,expected", [
    ({"groups": None}, "no_groups_claim"),
    ({"groups": ["other"]}, "not_in_group"),
    ({"preferred_username": "nobody@x.com"}, "unknown_user"),
])
def test_callback_reports_each_gate_with_its_own_code(client, monkeypatch,
                                                      claims_over, expected):
    _user()
    _start_flow(client, monkeypatch, claims=_claims(**claims_over))
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == f"/login?sso_error={expected}"
    assert client.get("/api/auth/me").status_code == 401


def test_callback_reports_an_inactive_user(client, monkeypatch):
    _user(active=False)
    _start_flow(client, monkeypatch)
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/login?sso_error=inactive_user"


def test_callback_reports_an_identity_mismatch(client, monkeypatch):
    _user(entra_oid="oid-original")
    _start_flow(client, monkeypatch)
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/login?sso_error=identity_mismatch"


def test_callback_never_returns_json_or_leaks_detail(client, monkeypatch):
    # The browser is doing a top-level navigation; a JSON body renders as a
    # blank page with text on it. And the provider's description can quote back
    # attacker-influenced input.
    _user()
    _start_flow(client, monkeypatch, raises=ValueError("AADSTS-secret-detail"))
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.status_code == 302
    assert r.headers["Location"] == "/login?sso_error=auth_failed"
    assert b"AADSTS" not in r.data


# ---------- the password door ----------

def test_password_login_is_403_when_sso_is_on(client, monkeypatch):
    _user()
    sso_env(monkeypatch)
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})
    assert r.status_code == 403
    assert "Microsoft" in r.get_json()["error"]


def test_password_login_still_works_on_an_incomplete_config(client, monkeypatch):
    # Fail closed on configuration: CAPRI_ENABLE_SSO=1 with a half-filled
    # config is a deployment mistake, and refusing every login over a typo is
    # worse than leaving password login up.
    _user()
    sso_env(monkeypatch, CAPRI_SSO_CLIENT_SECRET=None)
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})
    assert r.status_code == 200


def test_password_login_reports_its_auth_method(client):
    _user()
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})
    assert r.get_json()["auth_method"] == "password"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sso_routes.py -q`
Expected: FAIL — 404s where 302s are expected, and `KeyError: 'auth_method'`

- [ ] **Step 3: Rewrite `backend/app/blueprints/auth.py`**

Replace the file's imports and `_user_json`, and add the routes:

```python
from flask import Blueprint, jsonify, request, redirect, session, current_app, abort
from flask_login import login_user, logout_user, current_user, login_required
from flask_wtf.csrf import generate_csrf

from app.schemas.auth import SetPasswordIn
from app.services import sso_service
from app.services.auth_service import authenticate, set_initial_password

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _user_json(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "roles": user.roles_list,
        "division_id": user.division_id,
        "must_change_password": user.must_change_password,
        # How this session signed in. The frontend uses it to skip the
        # forced-password-change redirect for SSO users, who have no password
        # to change (app/__init__.py does the same server-side).
        "auth_method": session.get("auth_method", "password"),
    }
```

Then change `login()` so the 403 is its first line:

```python
@bp.post("/login")
def login():
    # FIRST line, before the body, the database or bcrypt: when SSO is
    # configured it is the only way in. Cheap, unreachable-around, and a
    # credential-stuffing run costs one string comparison instead of a hash.
    if sso_service.sso_config() is not None:
        return jsonify(error="Password sign-in is disabled. Use Sign in with Microsoft."), 403
    data = request.get_json(silent=True) or {}
    result = authenticate(data.get("email", ""), data.get("password", ""))
    if not result.ok:
        return jsonify(error=result.error), 401
    # remember=True issues a persistent cookie so email deep links still work
    # after the browser session ends (lifetime: REMEMBER_COOKIE_DURATION).
    login_user(result.user, remember=True)
    session["auth_method"] = "password"
    return jsonify(_user_json(result.user))
```

Then append the three SSO routes:

```python
@bp.get("/config")
def auth_config():
    """Unauthenticated: tells the login screen whether to offer SSO.

    This has to exist and has to be open -- /api/auth/me returns 401 before
    login, so the login screen has no other way to learn which form to draw. It
    leaks one boolean, which is visible from the login page anyway.
    """
    return jsonify(ok=True, sso_enabled=sso_service.sso_config() is not None)


@bp.get("/sso/login")
def sso_login():
    cfg = sso_service.sso_config()
    if cfg is None:
        abort(404)  # not 403: with SSO off this entry point does not exist
    try:
        flow = sso_service.build_auth_flow(cfg)
    except Exception as e:
        current_app.logger.warning("SSO could not start: %s", e)
        return redirect("/login?sso_error=auth_failed")
    session["sso_flow"] = flow
    session["sso_next"] = sso_service.safe_next_path(request.args.get("next"))
    return redirect(flow["auth_uri"])


@bp.get("/sso/callback")
def sso_callback():
    cfg = sso_service.sso_config()
    if cfg is None:
        abort(404)
    # pop, not get: a flow is single-use, and leaving it in the session invites
    # replay of the callback URL.
    flow = session.pop("sso_flow", None)
    nxt = session.pop("sso_next", "") or "/"
    try:
        if not flow:
            # Someone hitting /callback directly, or after the session expired.
            raise sso_service.SsoError("auth_failed", "no flow in session")
        claims = sso_service.redeem(cfg, flow, request.args)
        user = sso_service.resolve_user(cfg, claims)
    except sso_service.SsoError as e:
        # The code is from a fixed vocabulary; the detail is logged, never
        # returned. Redirect rather than JSON: this is a top-level navigation,
        # and a JSON body renders as a blank page with text on it.
        current_app.logger.warning("SSO refused (%s): %s", e.code, e)
        return redirect(f"/login?sso_error={e.code}")
    session.permanent = True
    # remember=False, unlike the password path: centralised revocation is much
    # of the point of SSO, and a 30-day cookie would outlive an Entra removal.
    login_user(user, remember=False)
    session["auth_method"] = "sso"
    return redirect(nxt)
```

- [ ] **Step 4: Add the startup warning**

In `backend/app/__init__.py`, inside `create_app`, immediately after `csrf.init_app(app)`:

```python
    # Fail open on the flag: CAPRI_ENABLE_SSO=1 with a half-filled config
    # behaves as SSO-off so a typo cannot lock every user out of a working app.
    # Log it, so the mistake is visible rather than silent.
    if os.environ.get("CAPRI_ENABLE_SSO", "").strip() == "1":
        from app.services.sso_service import sso_config
        if sso_config() is None:
            app.logger.warning(
                "CAPRI_ENABLE_SSO=1 but the SSO configuration is incomplete - "
                "SSO is DISABLED and password login remains active. Check "
                "CAPRI_SSO_TENANT_ID, _CLIENT_ID, _CLIENT_SECRET, "
                "_ALLOWED_GROUPS and _REDIRECT_URI.")
```

`os` is already imported at the top of that file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_sso_routes.py -q`
Expected: PASS — 24 passed

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 402 passed (361 + 24 route tests + 17 from Tasks 4-5).

`test_auth_api.py` and `test_password_change.py` must still pass untouched — they assert the password path, which the `_no_ambient_sso` fixture keeps SSO-off for.

- [ ] **Step 7: Commit and push**

```bash
git add backend/app/blueprints/auth.py backend/app/__init__.py backend/tests/test_sso_routes.py
git commit -m "feat(sso): auth config, sso/login and sso/callback routes

Three routes on the existing auth blueprint, which already owns /api/auth. The
guide mandates these exact paths because every D&H login screen reads them.

GET /config is unauthenticated by necessity: /api/auth/me 401s before login, so
the login screen has no other way to learn which form to draw. Both SSO routes
404 rather than 403 when the flag is off -- with SSO off they do not exist.

The callback pops the flow rather than reading it, because a flow is single-use
and leaving it invites replay; a test drives a real sign-in then replays the
same URL. A missing flow fails closed. Every refusal is a redirect to
/login?sso_error=<code>, never JSON: the browser is mid-navigation, and a JSON
body renders as a blank page. CAPRI redirects to /login rather than the guide's
/ because / is inside ProtectedLayout, which would bounce to /login?next=/ and
discard the code.

SSO sign-in uses remember=False where the password path keeps remember=True:
centralised revocation is much of the point of SSO, and a 30-day cookie would
outlive an Entra removal by weeks. Deep links survive via ?next=.

POST /login gains the 403 as its literal first line, before the body, the
database or bcrypt, so credential stuffing costs one string comparison.

_user_json reports auth_method so the frontend can skip the
forced-password-change redirect for SSO users. create_app logs a WARNING when
the flag is on but the config is incomplete.

Verified: 24 new tests pass; backend suite 402 passed, with test_auth_api and
test_password_change untouched.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

### Task 7: Let SSO users past the forced-password-change gate

`_require_password_change` 403s the whole API for a `must_change_password` user, exempting only the set-password endpoints. Under SSO-only there is no password form to escape through, so an admin-created user would be locked out of everything with no route forward.

**Files:**
- Modify: `backend/app/__init__.py` (the `_require_password_change` before_request)
- Test: `backend/tests/test_password_change.py`

**Interfaces:**
- Consumes: `session["auth_method"]` from Task 6.
- Produces: no new names. Behaviour: the gate is skipped when `session.get("auth_method") == "sso"`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_password_change.py`. `_flagged_user(app, email=...)` and `_login(client, app)` already exist at the top of this file.

```python
def test_sso_session_is_not_gated_by_the_password_flag(client, app, monkeypatch):
    """An SSO user with must_change_password set must still reach the API.

    Under SSO-only there is no password form to escape through, so without this
    skip an admin-created user is 403'd out of everything with no route
    forward. The flag stays ON the row deliberately -- it still bites if
    CAPRI_ENABLE_SSO is ever set back to 0.
    """
    from tests.test_sso import FakeMsalApp, sso_env, use_fake

    user = _flagged_user(app, email="sso@x.com")
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    client.get("/api/auth/sso/login")
    use_fake(monkeypatch, FakeMsalApp(result={"id_token_claims": {
        "preferred_username": "sso@x.com", "groups": ["group-a"], "oid": "oid-1",
    }}))
    assert client.get("/api/auth/sso/callback?code=c&state=st").status_code == 302

    assert client.get("/api/requests").status_code == 200
    db.session.refresh(user)
    assert user.must_change_password is True   # skipped, not cleared


def test_password_session_is_still_gated(client, app):
    # The existing behaviour must not regress: a password session with the flag
    # set is still 403'd.
    _flagged_user(app)
    _login(client, app)
    assert client.get("/api/requests").status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_password_change.py -q`
Expected: FAIL — `test_sso_session_is_not_gated_by_the_password_flag` gets 403 from `/api/requests`

- [ ] **Step 3: Add the skip**

In `backend/app/__init__.py`, add `session` to the flask import:

```python
from flask import Flask, jsonify, send_from_directory, abort, request, session
```

Then change the guard:

```python
    # A user flagged must_change_password may only hit the endpoints needed
    # to set a new password (or leave); everything else on the API is 403.
    exempt = {"auth.set_password", "auth.me", "auth.csrf_token", "auth.logout", "auth.login"}

    @app.before_request
    def _require_password_change():
        from flask_login import current_user
        if (request.blueprint is not None
                and current_user.is_authenticated
                and current_user.must_change_password
                # An SSO session has no password to change, so gating it would
                # lock the user out of everything with no form to escape
                # through. The flag stays on the row, so it still applies if
                # CAPRI_ENABLE_SSO is ever set back to 0.
                and session.get("auth_method") != "sso"
                and request.endpoint not in exempt):
            return jsonify(error="You must set a new password before continuing.",
                           code="PASSWORD_CHANGE_REQUIRED"), 403
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_password_change.py -q`
Expected: PASS — 8 passed

- [ ] **Step 5: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 404 passed (402 + 2 new)

- [ ] **Step 6: Commit and push**

```bash
git add backend/app/__init__.py backend/tests/test_password_change.py
git commit -m "fix(sso): skip the forced-password-change gate for SSO sessions

_require_password_change 403s the whole API for a must_change_password user,
exempting only the set-password endpoints. Under SSO-only there is no password
form to escape through, so an admin-created user was locked out of everything
with no route forward.

The flag is skipped, not cleared: it still applies if CAPRI_ENABLE_SSO is ever
set back to 0, which is the documented recovery lever.

Verified: an SSO session with the flag set reaches /api/requests while a
password session with the same flag is still 403'd; backend suite 404 passed.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

### Task 8: The tri-state login screen

**Files:**
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/auth/ProtectedLayout.tsx`
- Modify: `frontend/src/routes/LoginPage.tsx`
- Test: `frontend/src/routes/LoginPage.test.tsx` (create)

**Interfaces:**
- Consumes: `GET /api/auth/config` and the `auth_method` field from Task 6.
- Produces: `AuthConfig` interface, `getAuthConfig()`, `CurrentUser.auth_method`, and `SSO_ERRORS` exported from `LoginPage.tsx` for the test.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/routes/LoginPage.test.tsx`:

```tsx
// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/auth', () => ({
  getAuthConfig: vi.fn(),
  login: vi.fn(),
}))
import { getAuthConfig } from '../api/auth'
import LoginPage from './LoginPage'

function renderPage(initial = '/login') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('LoginPage sign-in modes', () => {
  beforeEach(() => { vi.mocked(getAuthConfig).mockReset() })

  it('shows neither form while the config is still loading', () => {
    // Defaulting to the password form would flash a box that then vanishes,
    // which reads as breakage and trains users to type credentials into a
    // disappearing form.
    vi.mocked(getAuthConfig).mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByText(/loading sign-in options/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /microsoft/i })).not.toBeInTheDocument()
  })

  it('offers only the Microsoft button when SSO is on', async () => {
    vi.mocked(getAuthConfig).mockResolvedValue({ ok: true, sso_enabled: true })
    renderPage()
    expect(await screen.findByRole('button', { name: /sign in with microsoft/i }))
      .toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })

  it('offers only the password form when SSO is off', async () => {
    vi.mocked(getAuthConfig).mockResolvedValue({ ok: true, sso_enabled: false })
    renderPage()
    expect(await screen.findByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /microsoft/i })).not.toBeInTheDocument()
  })

  it('falls back to the password form when the config call fails', async () => {
    // If the config call fails the server is probably down, and the password
    // form at least produces a comprehensible error.
    vi.mocked(getAuthConfig).mockRejectedValue(new Error('offline'))
    renderPage()
    expect(await screen.findByLabelText(/password/i)).toBeInTheDocument()
  })
})

describe('LoginPage sso_error messages', () => {
  beforeEach(() => {
    vi.mocked(getAuthConfig).mockReset()
    vi.mocked(getAuthConfig).mockResolvedValue({ ok: true, sso_enabled: true })
  })

  it.each([
    ['not_in_group', /authorized security group/i, /contact it/i],
    ['no_groups_claim', /no group information/i, /contact it/i],
    ['unknown_user', /isn't set up in capri/i, /admin/i],
    ['inactive_user', /deactivated/i, /admin/i],
    ['identity_mismatch', /doesn't match the account on file/i, /contact it/i],
    ['auth_failed', /failed or was cancelled/i, /try again/i],
  ])('explains %s and names who fixes it', async (code, message, fixer) => {
    renderPage(`/login?sso_error=${code}`)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).toHaveTextContent(fixer)
  })

  it('falls back to a generic message for an unknown code', async () => {
    renderPage('/login?sso_error=something_new')
    expect(await screen.findByRole('alert'))
      .toHaveTextContent(/microsoft sign-in failed/i)
  })

  it('shows no alert when there is no sso_error', async () => {
    renderPage('/login')
    await screen.findByRole('button', { name: /microsoft/i })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

From `frontend/`:
Run: `node ./node_modules/vitest/vitest.mjs run src/routes/LoginPage.test.tsx`
Expected: FAIL — `getAuthConfig` is not exported from `../api/auth`

- [ ] **Step 3: Extend the auth API module**

In `frontend/src/api/auth.ts`, add `auth_method` to `CurrentUser` and the new call:

```ts
export interface CurrentUser {
  id: string
  name: string
  email: string
  roles: string[]
  division_id: string | null
  must_change_password: boolean
  /** How this session signed in. SSO users have no password to change. */
  auth_method: 'sso' | 'password'
}

export interface AuthConfig {
  ok: boolean
  sso_enabled: boolean
}

/** Unauthenticated: tells the login screen whether to offer SSO. */
export function getAuthConfig(): Promise<AuthConfig> {
  return api<AuthConfig>('/auth/config')
}
```

- [ ] **Step 4: Stop `ProtectedLayout` redirecting SSO users to the password screen**

In `frontend/src/auth/ProtectedLayout.tsx`, line 13:

```tsx
  // An SSO session has no password to change, so sending them to
  // /change-password would ask them to invent one nothing uses. The server
  // skips the same gate in app/__init__.py.
  if (data.must_change_password && data.auth_method !== 'sso')
    return <Navigate to="/change-password" replace />
```

- [ ] **Step 5: Rewrite `LoginPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getAuthConfig, login } from '../api/auth'
import { safeNext } from '../auth/loginRedirect'
import { ApiError } from '../api/client'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { PasswordInput } from '../components/ui/PasswordInput'
import { Lockup } from '../components/Lockup'

/* Each message names WHO fixes it -- IT for a group or identity problem, an app
   admin for a missing or deactivated row, the user for a cancelled sign-in.
   That single detail removes most of the support traffic this feature would
   otherwise generate. */
export const SSO_ERRORS: Record<string, string> = {
  not_in_group:
    "Your Microsoft account isn't in the authorized security group. Contact IT to request access.",
  no_groups_claim:
    'Microsoft sign-in succeeded but no group information was returned. Contact IT.',
  unknown_user:
    "Your Microsoft account isn't set up in CAPRI yet. Ask an admin to add your user.",
  inactive_user: 'Your account is deactivated. Contact an admin.',
  identity_mismatch:
    "This Microsoft account doesn't match the account on file for your email address. Contact IT.",
  auth_failed: 'Microsoft sign-in failed or was cancelled. Please try again.',
}

/* Microsoft's mark keeps its official four colours, so it is inlined here
   rather than added to NavIcons/ActionIcons, which are currentColor line
   icons on a 24px grid. */
function MicrosoftMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" className="shrink-0">
      <rect x="0" y="0" width="8" height="8" fill="#F25022" />
      <rect x="10" y="0" width="8" height="8" fill="#7FBA00" />
      <rect x="0" y="10" width="8" height="8" fill="#00A4EF" />
      <rect x="10" y="10" width="8" height="8" fill="#FFB900" />
    </svg>
  )
}

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [ssoError, setSsoError] = useState<string | null>(null)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const qc = useQueryClient()

  /* Tri-state, not boolean: SSO-on means SSO *only*, so rendering the password
     form before we know would flash a form that then disappears. isPending IS
     the third state, so no extra bookkeeping is needed. A failed call falls
     back to the password form, which at least gives a comprehensible error. */
  const { data: authConfig, isPending: configPending } = useQuery({
    queryKey: ['auth-config'], queryFn: getAuthConfig, retry: false,
  })
  const ssoEnabled = configPending ? null : (authConfig?.sso_enabled ?? false)

  /* Translate the code the callback redirected with, then strip it so a
     refresh does not resurrect a stale error. Any ?next= is preserved. */
  useEffect(() => {
    const code = searchParams.get('sso_error')
    if (!code) return
    setSsoError(SSO_ERRORS[code] ?? 'Microsoft sign-in failed.')
    const rest = new URLSearchParams(searchParams)
    rest.delete('sso_error')
    setSearchParams(rest, { replace: true })
  }, [searchParams, setSearchParams])

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (user) => {
      qc.setQueryData(['me'], user)
      navigate(user.must_change_password ? '/change-password' : safeNext(searchParams.get('next')),
        { replace: true })
    },
  })

  const error =
    ssoError ??
    (mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? 'Login failed.'
        : null)

  function startSso() {
    const next = safeNext(searchParams.get('next'))
    // A top-level navigation, not a fetch: the browser has to follow the
    // redirect chain out to Entra and back.
    window.location.assign(`/api/auth/sso/login?next=${encodeURIComponent(next)}`)
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <div className="w-full max-w-sm rounded-xl border border-border bg-surface p-6 shadow-sm">
        <div className="mb-6">
          {/* Left-justified, matching the brand lockup artwork. */}
          <Lockup
            panel
            markSize={72}
            subtitle="Capital Approval, Planning, Reporting & Investment"
            className="w-full"
          />
        </div>

        {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400" role="alert">{error}</p>}

        {ssoEnabled === null && (
          <p className="text-sm text-muted">Loading sign-in options…</p>
        )}

        {ssoEnabled === true && (
          <Button type="button" className="w-full" onClick={startSso}>
            <span className="inline-flex items-center justify-center gap-2">
              <MicrosoftMark />
              Sign in with Microsoft
            </span>
          </Button>
        )}

        {ssoEnabled === false && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); mutation.mutate() }}>
            <div className="space-y-1">
              <label htmlFor="email" className="text-sm font-medium">Email</label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                autoComplete="email" required />
            </div>
            <div className="space-y-1">
              <label htmlFor="password" className="text-sm font-medium">Password</label>
              <PasswordInput id="password" value={password}
                onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            </div>
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              {mutation.isPending ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        )}
      </div>
    </main>
  )
}
```

- [ ] **Step 6: Run the new tests**

From `frontend/`:
Run: `node ./node_modules/vitest/vitest.mjs run src/routes/LoginPage.test.tsx`
Expected: PASS — 12 passed

- [ ] **Step 7: Fix the existing test mocks**

`CurrentUser` gained a required field, so every test building a full user object needs it. Add `auth_method: 'password'` to the `useMe` mocks in:

- `src/components/PingDetail.test.tsx`
- `src/components/PingPanel.test.tsx`
- `src/routes/MessagesPage.test.tsx`
- `src/routes/ReportsPage.test.tsx`
- `src/routes/RequestsListPage.test.tsx`

Run: `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
Expected: no errors. If any remain, they name the file and the missing property.

- [ ] **Step 8: Run the full frontend suite and build**

From `frontend/`:
Run: `node ./node_modules/vitest/vitest.mjs run`
Expected: all tests pass.

Run: `node ./node_modules/vite/bin/vite.js build`
Expected: builds into `frontend/dist`.

- [ ] **Step 9: Commit and push**

```bash
git add frontend/src/api/auth.ts frontend/src/auth/ProtectedLayout.tsx frontend/src/routes/LoginPage.tsx frontend/src/routes/LoginPage.test.tsx frontend/src/components/PingDetail.test.tsx frontend/src/components/PingPanel.test.tsx frontend/src/routes/MessagesPage.test.tsx frontend/src/routes/ReportsPage.test.tsx frontend/src/routes/RequestsListPage.test.tsx
git commit -m "feat(sso): tri-state login screen with the Microsoft button

The login screen asks /api/auth/config which mode it is in and renders one of
three states. Tri-state rather than boolean because SSO-on means SSO only:
defaulting to false would flash a password form that then vanishes, which reads
as breakage and trains users to type credentials into a disappearing form.
TanStack Query's isPending is the third state, so it needs no extra state.
A failed config call falls back to the password form.

Each sso_error code maps to a sentence that names who fixes it -- IT for a
group or identity problem, an app admin for a missing or deactivated row, the
user for a cancelled sign-in -- then the parameter is stripped so a refresh
does not resurrect a stale error. Any ?next= is preserved and carried into
/sso/login, so an emailed deep link survives the round trip.

ProtectedLayout no longer sends SSO sessions to /change-password, matching the
server-side skip: there is no password to change.

Microsoft's mark is inlined rather than added to NavIcons/ActionIcons, which
are currentColor line icons; the mark has to keep its official colours.

Verified: 12 new vitest cases pass; tsc clean after adding auth_method to the
five existing useMe mocks; full frontend suite passes and vite build succeeds.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

### Task 9: The IT request, the support runbook and CLAUDE.md

**Files:**
- Create: `docs/it-requests/2026-09-21-capri-entra-sso.md`
- Create: `docs/sso-support-runbook.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the env var names and error codes from every prior task.
- Produces: documentation only. No code.

- [ ] **Step 1: Write the IT request**

Create `docs/it-requests/2026-09-21-capri-entra-sso.md`. Model it on APEX's `../apex/docs/it-requests/2026-09-21-entra-sso-email.md`. It must contain:

- **A request for CAPRI's own app registration**, stating why it is not a change to ARIA's or APEX's: redirect URIs and secret rotation are per-app, and sharing one means another app's rotation breaks CAPRI.
- **The five values**, in a table mapping each to its env var: Directory (tenant) ID → `CAPRI_SSO_TENANT_ID`; Application (client) ID → `CAPRI_SSO_CLIENT_ID`; client secret **via a secure channel, never email** → `CAPRI_SSO_CLIENT_SECRET`; the group object ID → `CAPRI_SSO_ALLOWED_GROUPS`; the redirect URI → `CAPRI_SSO_REDIRECT_URI`.
- **One redirect URI to register**, exactly: `http://localhost:5100/api/auth/sso/callback`. Note CAPRI is a single Flask server on one port, so unlike APEX there is only one. Note Entra matches literally — scheme, host, port, path, no trailing slash.
- **The group:** `SEC-App-Capri-Dev`, which Bryan already owns, so its object ID and membership are **not** an IT ask. What **is** an IT ask is **assigning that group to the new app registration**, which needs rights over the registration rather than over the group.
- **The `groups` claim must be emitted:** Token configuration → *Groups assigned to the application*. Explain that without it every sign-in fails at gate 1 with `no_groups_claim` and looks like an app bug; and that *All groups* is worse, because a user in many groups overflows the claim and Entra sends a link instead of the list, so the claim goes missing for exactly the most-connected users.
- **The object-ID trap, prominently:** `CAPRI_SSO_ALLOWED_GROUPS` takes object IDs (GUIDs), not display names. Pasting `SEC-App-Capri-Dev` fails every sign-in at gate 2 as `not_in_group`, which reads as an access-request problem and sends you to IT for a one-line configuration typo.
- **A note that there is no deployed HTTPS environment yet**, so only the localhost URI is needed now; when CAPRI is deployed it will need a DNS name and HTTPS, because Entra accepts `http://` only for `localhost` and a bare LAN address like `http://172.16.x.x:8081` cannot be registered at all.
- **Who owns the client secret expiry date**, with a calendar reminder, since an expired secret is a total outage with no in-app warning.
- **A note not to commit the user list to the repo** — it mirrors to GitHub, so staff addresses are attached to the email instead.

- [ ] **Step 2: Write the support runbook**

Create `docs/sso-support-runbook.md`. It must contain:

- **The recovery procedure, first and unmissable:** set `CAPRI_ENABLE_SSO=0` and restart. Locally that is one line in `backend/.env`. State plainly that the moment you need this is the moment nobody can sign in to look it up, which is why it is at the top.
- **Granting a user access is two steps:** membership of `SEC-App-Capri-Dev` **and** an active row in CAPRI with the same work email. Note the error messages tell you which step is missing.
- **The failure-mode table**, from guide §11 adapted to CAPRI:

| Symptom / code | Actual cause | Who fixes it |
|---|---|---|
| `no_groups_claim` | Token configuration does not emit `groups`, or the claim overflowed (use *Groups assigned to the application*), or the user is in no groups | IT |
| `not_in_group` | Not a member of an authorizing group, or `CAPRI_SSO_ALLOWED_GROUPS` holds a display name or the wrong object ID | IT |
| `unknown_user` | No row in CAPRI for that email, or the email differs from the Entra one | App admin |
| `inactive_user` | Row exists but is deactivated | App admin |
| `identity_mismatch` | `users.entra_oid` was pinned to a different Entra identity — a recycled or reassigned address, or the row was pinned by the wrong person | IT, then app admin |
| `auth_failed` | Cancelled at the Microsoft screen, expired session, replayed callback, or an MSAL error — commonly a redirect-URI mismatch or an expired client secret | User retries, then IT |
| SSO button never appears | `sso_config()` returned `None` — a missing variable. Check the startup WARNING | Deployer |
| Sign-in loops back to login | Session cookie not persisting — `SECRET_KEY` changing on restart, or a proxy stripping the cookie | Developer |
| Whole suite 403s on login | A developer `.env` leaking into tests; the `_no_ambient_sso` fixture in `conftest.py` prevents it | Developer |
| Everyone locked out | Entra outage, expired secret, or a bad config | `CAPRI_ENABLE_SSO=0`, restart |

- **Which environment is in which mode**, written down: local dev runs password login with the flag unset; there is no deployed environment yet.
- **How to clear a wrongly pinned `entra_oid`**: `UPDATE users SET entra_oid = NULL WHERE email = '…'`, which lets the next SSO sign-in re-pin it. Note this is the only way out of `identity_mismatch` and that it should be done only after confirming who the account belongs to.

- [ ] **Step 3: Update CLAUDE.md**

Add an **Entra ID SSO** section after "Roles & approval workflow". It must state:

- SSO is **off** unless `CAPRI_ENABLE_SSO=1` **and** all five `CAPRI_SSO_*` values are present; `sso_config() is not None` is the single switch, and not-None also means password login returns 403.
- The six env vars, and that they live in `backend/.env` (git-ignored).
- `app/services/sso_service.py` is the **only** module importing `msal`; routes stay thin in `blueprints/auth.py`.
- The four gates and their six error codes, with the note that gate order is load-bearing because each code names a different fixer.
- **`sso_config()` reads `os.environ` at call time and must not become a `Config` class attribute** — `config.py`'s import-time pattern would make it untestable and let a developer's `.env` 403 the whole suite (the `_no_ambient_sso` fixture in `conftest.py` is the guard).
- Failures redirect to **`/login?sso_error=…`**, not `/`, because `/` is inside `ProtectedLayout`, which would bounce to `/login?next=/` and discard the code.
- `response_mode` must stay **query/GET**: `SESSION_COOKIE_SAMESITE="Lax"` would starve a `form_post` callback of its session cookie and break every sign-in while looking like an Entra problem.
- SSO sessions use `remember=False` (the password path keeps `remember=True`), and `_require_password_change` skips `auth_method == "sso"` sessions — with `auth_method` carried on `/api/auth/me` so `ProtectedLayout` skips it too.
- `users.entra_oid` is nullable and **not** unique, and `users.reset_token` uses a filtered unique index on SQL Server (migration `b8c9d0e1f2a3`) because a plain nullable-unique column caps the table at one NULL there.
- Pointers to the spec, the guide, the runbook and the IT request.

- [ ] **Step 4: Verify nothing is stale**

Re-read the three documents against the code as built. Check specifically:
- Every env var name matches `sso_service.sso_config()` exactly.
- Every error code matches `sso_service.ERROR_CODES` exactly.
- The redirect URI matches the port Flask actually runs on (5100).
- The migration revision IDs match the files created in Tasks 1 and 2.

- [ ] **Step 5: Commit and push**

```bash
git add docs/it-requests/2026-09-21-capri-entra-sso.md docs/sso-support-runbook.md CLAUDE.md
git commit -m "docs(sso): IT request, support runbook and CLAUDE.md section

The IT request asks for CAPRI's own app registration, lists the five values
against their env vars, and leads with the two things that actually break
sign-ins: the groups claim must be emitted via 'Groups assigned to the
application', and CAPRI_SSO_ALLOWED_GROUPS takes object IDs rather than display
names -- a display name fails every sign-in as not_in_group, which reads as an
access problem and sends you to IT for a typo. Only one redirect URI is needed,
since CAPRI is a single server on one port.

The runbook leads with the CAPRI_ENABLE_SSO=0 recovery, because the moment you
need it is the moment nobody can sign in to look it up. It also records that
granting access is two steps, group and row, and how to clear a wrongly pinned
entra_oid.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push origin main && git push azure main:dev
```

---

## Final verification

After Task 9, confirm the whole thing from a clean state.

- [ ] **Backend suite:** from `backend/`, `.venv/Scripts/python.exe -m pytest -q` → 404 passed.
- [ ] **Typecheck:** from `frontend/`, `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` → clean.
- [ ] **Frontend suite:** from `frontend/`, `node ./node_modules/vitest/vitest.mjs run` → all pass.
- [ ] **Build:** from `frontend/`, `node ./node_modules/vite/bin/vite.js build` → succeeds.
- [ ] **Migrations reach head on both dialects:** `flask db upgrade` with `AZURE_SQL_ODBC` set, and again with it commented out against SQLite. Both reach `c9d0e1f2a3b4`.
- [ ] **SSO is genuinely off.** Start the app (`Start CAPRI.cmd` or `run-app.ps1`) with no `CAPRI_*` variables set, then:
  - `GET /api/auth/config` → `{"ok": true, "sso_enabled": false}`
  - `GET /api/auth/sso/login` → **404**
  - `GET /api/auth/sso/callback` → **404**
  - Sign in at `http://localhost:5100` with `admin@uniteduptime.com` / `ChangeMe123!` → the **password form** is shown and works.
- [ ] **The flag alone changes nothing.** Set only `CAPRI_ENABLE_SSO=1` in `backend/.env`, restart, and confirm: a startup `WARNING` names the missing variables, `sso_enabled` is still `false`, and password login still works. Then remove the line.

**Do not** put real Entra values anywhere in the repo, and do not enable the flag on any shared environment. That is Step 1 onward, gated on the IT request.
