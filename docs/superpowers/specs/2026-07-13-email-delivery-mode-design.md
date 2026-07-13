# Email delivery mode (Test / Live)

**Date:** 2026-07-13

## Context

Notification emails are currently redirected to a single tester
(`EMAIL_REDIRECT_TO`, default `bryan.farrell@uniteduptime.com`) whenever that
env var is set — controlled only at deploy time, with no runtime switch. Admins
need a UI toggle to switch delivery between **Test mode** (redirect everything
to a test recipient — current behavior) and **Live mode** (send to the real
recipients: approvers, requestors, finance).

## Backend

- **Storage:** the existing `AppSetting` key/value table (already migrated — no
  new migration). Keys:
  - `email_mode` — `"test"` | `"live"` (default `"test"`)
  - `email_test_recipient` — address for test redirects (default: the app's
    `EMAIL_REDIRECT_TO` config value)
- **`settings_service.py`** (new): `get_email_settings()` →
  `{ "mode": ..., "test_recipient": ... }` reading `AppSetting` with fallback to
  config defaults when a row is absent; `set_email_settings(mode, recipient)`
  upserts both rows. Because the default is Test + the current redirect address,
  first-run behavior is unchanged.
- **`notify.py`:** replace direct `EMAIL_REDIRECT_TO` reads. Both `_emit` and
  `_emit_plain` compute the recipient from `settings_service`:
  - Test → send to `test_recipient`; `_redirect_note` shows the existing
    "Intended recipient: … (redirected while testing)" banner.
  - Live → send to the real `intended`; no banner.
  - `EMAIL_ENABLED` is unchanged — still the master gate on whether Outlook
    sends at all; mode only changes the recipient.
- **API** (ADMIN-only, in the `email_templates` blueprint):
  - `GET /api/email-templates/settings` → `{ mode, test_recipient }`
  - `PUT /api/email-templates/settings` — body validated by a Pydantic
    `EmailSettingsIn` (mode ∈ {`test`,`live`}; `test_recipient` a valid email).
    Raises `ServiceError` on bad input.

## Frontend

- **`components/admin/EmailDeliveryMode.tsx`** (new): a self-contained panel —
  loads settings via TanStack Query, renders a Test/Live control, the editable
  test-recipient field (shown in Test mode), and a Save. Switching to **Live**
  fires a `window.confirm` ("Real emails will be sent to actual recipients.
  Continue?"); switching back to Test is instant. Saving `PUT`s and invalidates
  the settings query.
- Rendered in **both** places: at the top of `EmailTemplatesPage` (list) and at
  the top of `EmailTemplateEditor` (above `TemplateTabs`).
- `api/emailTemplates.ts`: add `getEmailSettings()` / `saveEmailSettings()` and
  an `EmailSettings` type.

## Testing

- Backend (`pytest`): `settings_service` defaults + round-trip; `notify`
  redirects to `test_recipient` in Test mode and to the real recipient in Live
  mode (extend `test_notify.py`); `EmailSettingsIn` validation; endpoint is
  ADMIN-only and round-trips.
- Frontend (`vitest`): `EmailDeliveryMode` — toggling to Live prompts confirm
  and only saves the live payload when confirmed; editing the recipient + Save
  posts the right body.
- Regression: `tsc`, full vitest, `pytest`, `vite build` green; visual check of
  the panel on both the list page and the editor.

## Out of scope
Changing `EMAIL_ENABLED`; per-template or per-recipient overrides; scheduling.
