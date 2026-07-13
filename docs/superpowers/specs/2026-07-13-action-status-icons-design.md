# Action & status icons rollout

**Date:** 2026-07-13
**Source:** `brand/UUS CAPEX Flow Nav Icons.html` → "Action & status icons" section

## Context

The brand document added an in-page icon set (approval actions, table/row
controls, workflow status) in the same line style as the nav icons already
shipped in `components/NavIcons.tsx`. Today the app's in-page controls are
almost entirely text-only, and `StatusBadge` shows colored pills without icons.
This rollout applies the new set so actions and status read consistently with
the brand, and adds the small amount of new UI the user approved (list search +
per-row view).

## Components

### `components/ActionIcons.tsx` (new)
Presentational SVG icon components, one per symbol, sharing a small local
`Icon` wrapper: `viewBox="0 0 24 24"`, `fill="none"`, `stroke="currentColor"`,
rounded caps/joins, `strokeWidth` prop (default 1.8; badges pass 2),
`aria-hidden`. Paths copied verbatim from the brand doc. `currentColor` means
each icon adopts its button/badge text color rather than a baked-in hue.

Icons: `ApproveIcon` (check-in-circle), `RejectIcon` (✕-in-circle),
`SubmitIcon` (arrow-to-bar), `ViewIcon` (eye), `EditIcon` (pencil),
`DeleteIcon` (trash), `DownloadIcon`, `SearchIcon`, `FilterIcon`,
`AddIcon` (circle-plus), `UploadIcon`, and status icons `DraftIcon`
(hourglass), `PendingIcon` (clock), `ApprovedIcon` (check), `RejectedIcon`
(✕). Return/Revise is omitted — this app has no separate return action.

### `components/ui/Badge.tsx`
`Badge` gains an optional `icon?: ReactNode` rendered before children.
`StatusBadge` maps status → status icon (DRAFT→Draft, PENDING_L*→Pending,
APPROVED→Approved, REJECTED→Rejected) at ~13px / strokeWidth 2. Tones are
unchanged (already slate/amber/green/red per doc).

### `routes/RequestDetailPage.tsx`
Prefix action controls with icons (icons inherit each control's color):
Approve→Approve, Reject→Reject, Resubmit→Submit, "Edit draft"→Edit,
"Delete draft"→Delete, "Upload"→Upload, attachment link→Download,
attachment "Remove"→Delete.

### `routes/WizardPage.tsx`
"+ Add line item"→Add, line "Remove"→Delete, Review submit button→Submit.

### `routes/RequestsListPage.tsx` + `RequestsTable`
- Add a client-side **search** box (SearchIcon) in the filter bar; filters the
  loaded rows via a new pure `filterRequests(rows, query)` in
  `routes/requestsSort.ts` (matches number / division_name / requestor_name,
  case-insensitive). Lives in `RequestsListPage` state so the Dashboard table
  is unaffected.
- Add a **Filter** icon labeling the existing status/scope filter bar.
- Add a trailing **View** column in `RequestsTable`: an eye button linking to
  `/requests/:id` (row number link stays).

## Testing
- `requestsSort.test.ts`: cases for `filterRequests` (match by each field,
  case-insensitive, blank query returns all, no match returns empty).
- `Badge` render test: each status renders correct label + an `svg` icon.
- Regression: `tsc`, `vite build`, full vitest green.
- Visual: drive the running app (list search, badges, detail actions, wizard).

## Out of scope
Nav icons (already shipped), the light-sidebar restyle, Return/Revise action,
replacing lucide sort chevrons / Sign-Out glyph.
