# Email-based login with default password — Design

**Date:** 2026-07-15
**Status:** Approved

## Goal

Sign-in switches from username to email address. New and reset accounts start
at a default password (`Welcome@1`) and must set their own password on first
login. This also positions the app for Entra ID SSO later (email/UPN is the
identifier Entra matches on); no SSO code is built now.

## Decisions (confirmed with Bryan)

1. **Username is removed entirely** — email is the sole identifier.
2. **Default password applies to new users and admin resets.** Existing
   accounts keep their current passwords until reset.
3. **Forced change is a full-screen page after login** (not inline on the
   login card).
4. **Enforcement is server-side** — the API blocks a flagged user, not just
   the SPA.

## Data model

- `User.username` column dropped (Alembic migration; SQLite batch mode so it
  also runs on the dev DB, plus Azure SQL in prod).
- `User.must_change_password: Mapped[bool]`, default `false`, added in the
  same migration.
- `DEFAULT_PASSWORD = "Welcome@1"` constant in `backend/app/config.py`.

## Backend behavior

- **Login** — `POST /api/auth/login` takes `email` + `password`;
  `auth_service.authenticate` looks the user up by (lowercased) email. The
  lockout/timing-equalization logic is unchanged. `_user_json` (login + `me`
  responses) drops `username` and adds `must_change_password`.
- **Create user** — `user_service.create_user` no longer takes `username` or
  `password`; uniqueness check is on email only. New users get
  `hash_password(DEFAULT_PASSWORD)` and `must_change_password = true`.
- **Admin reset** — `admin_reset_password(user_id, password)` becomes a
  reset-to-default: sets the default password, sets the flag, clears
  lockout counters. No password is supplied by the admin.
- **Set password** — new `POST /api/auth/set-password` (login required).
  Only valid while `must_change_password` is set (else 400). Takes
  `new_password`: min 8 chars, must not equal `DEFAULT_PASSWORD`. Sets the
  hash, clears the flag.
- **Profile change-password** also clears the flag — defense-in-depth so the
  flag can never survive a successful password change, whichever path set it.
- **Enforcement** — an app-level `before_request`: if the current user is
  authenticated and flagged, any `/api` endpoint other than
  `auth.set_password`, `auth.me`, `auth.csrf`, `auth.logout` returns
  `403 {"error": ..., "code": "PASSWORD_CHANGE_REQUIRED"}`. Static/SPA
  routes are not blocked (the SPA itself must load).

## Frontend behavior

- **LoginPage** — Username field becomes Email (`type="email"`,
  `autoComplete="email"`); API call sends `email`.
- **ChangePasswordPage** — new full-screen card at `/change-password`
  (login-card styling: Logo, brand header). Fields: new password + confirm
  (both `PasswordInput`), client checks match + min 8. Calls
  `set-password`, then invalidates `me` and navigates to the dashboard.
- **Routing/gating** — after login (and in `ProtectedLayout`), a user whose
  `me.must_change_password` is true is redirected to `/change-password`.
  The API client treats a 403 with code `PASSWORD_CHANGE_REQUIRED` like the
  existing 401 handling, but redirects to `/change-password`.
- **Admin Users screens** — Users list drops the Username column; UserForm
  drops the Username and Temporary-password fields; the create flow shows a
  note that the account starts at the default password and must change it.
  UserEditPage's reset action becomes a single "Reset to default password"
  button (confirm dialog, no input).
- **Types** — `AdminUser`/`UserInput`/`Me` types updated accordingly.

## Seed & dev login

`seed.py` creates the admin as `admin@uniteduptime.com / ChangeMe123!` with
`must_change_password = false` so local development stays a one-step login.
CLAUDE.md's dev-login line is updated.

## Out of scope

- Entra ID SSO (future phase; this design only ensures email is the identity).
- Password complexity rules beyond min-8 + not-the-default.
- Password expiry, history, or self-service "forgot password" changes.

## Testing

- Backend pytest: existing auth/user tests updated for email login; new tests
  for: login by email, create-user gets default+flag, admin reset sets
  default+flag, set-password happy path + rejections (too short, equals
  default, flag not set), 403 gating of other endpoints while flagged,
  profile change clears flag.
- Frontend: typecheck (`tsc`) + `vite build`; vitest for any touched
  component tests.
