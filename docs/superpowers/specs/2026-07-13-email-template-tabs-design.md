# Email template tabs

**Date:** 2026-07-13

## Context

Admins edit four notification email templates under **Admin → Email Templates**.
Today the sidebar link opens a list page; clicking a template opens its editor
at `/admin/email-templates/:type`. To switch to another template you must
navigate back to the list and pick again. This adds a tab bar at the top of the
editor so all templates are reachable in place.

## Behavior

- **Tab bar** at the top of `EmailTemplateEditor` (above the title/actions row),
  one tab per template, in the list's order. The active tab (current `:type`)
  gets the accent style; a disabled template shows a small muted "off" dot.
- Data comes from the existing `listEmailTemplates` query (cached under
  `['email-templates']`) — no new API, model, or backend change.
- Clicking a tab navigates to `/admin/email-templates/:type`; the editor already
  reloads its fields from the route param via its `useEffect([data])`.
- **Unsaved-edits guard:** clicking a *different* tab while the editor is
  `dirty` triggers `window.confirm("You have unsaved changes. Discard them and
  switch?")` (same pattern as the "Delete draft" confirm). Confirm → navigate;
  cancel → stay. Clicking the active tab is a no-op.
- The list page (`EmailTemplatesPage`) and sidebar links are unchanged.

## Components

- `EmailTemplateEditor.tsx` — add the tab bar. Factor the tabs into a small
  local `TemplateTabs` piece driven by `{ templates, activeType, dirty }` that
  renders `NavLink`/buttons and applies the confirm-guard on switch.

## Testing

- Editor component test: with unsaved edits, clicking another tab calls
  `window.confirm` and navigates only when confirmed; when not dirty it
  navigates without a prompt; the active tab is marked current.
- Regression: `tsc`, full vitest, `vite build` green; visual check in the app.

## Out of scope
Backend/API/model changes; the list page; changing what the editor saves.
