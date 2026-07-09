# ARIA-style frontend restyle — design

**Date:** 2026-07-08
**Status:** Approved

## Goal

Give the CAPEX Tracking frontend the look and feel of the reference app "ARIA"
(two screenshots provided): a polished SaaS dashboard with a navy grouped
sidebar, a rich header, light-gray content area, white KPI stat cards, clean
tables with pill status badges, and blue accents — plus a working light/dark
theme toggle.

Stack is unchanged: React 19 + React Router 7 + TanStack Query + Tailwind v4.
One new dependency: `lucide-react` for nav/section icons.

No backend changes. No charts (ARIA's donut/bar are AR-analytics-specific and
absent from the CAPEX data model). We match the visual language, not chart
content.

## Decisions

- **Scope:** whole app — shared shell + UI primitives, so every page inherits.
- **Dark mode:** working, persisted per browser (localStorage), toggled in header.
- **Dashboard KPIs:** add a StatCard row computed client-side from data already
  fetched; no new API.
- **Icons:** add `lucide-react`.
- **Header:** text-only lockup — **no logo mark** (per brand guidance
  "color only, no logo mark"). Deliberate deviation from ARIA.

## Architecture

### Design tokens & theming (`src/index.css`)
Semantic color tokens exposed as Tailwind v4 `@theme` variables so components
use meaning-based utilities (`bg-bg`, `bg-surface`, `text-fg`, `text-muted`,
`border-border`, `bg-sidebar`, `text-accent`, …) instead of hard-coded
`slate-*`. Built from the existing brand palette (navy `#0B2A4A`, blue
`#2E6DF0`, sky `#8FB2FF`) — no new brand colors.

Dark mode via `@custom-variant dark (&:where(.dark, .dark *))` plus a `.dark`
block that overrides the same token variables. Because Tailwind v4 emits theme
vars as CSS custom properties, overriding them under `.dark` re-themes every
token-based utility with near-zero per-component churn.

Token set (light / dark):

| token | light | dark |
|-------|-------|------|
| `--color-bg` | `#f1f5f9` | `#0b1220` |
| `--color-surface` | `#ffffff` | `#1e293b` |
| `--color-border` | `#e2e8f0` | `#334155` |
| `--color-fg` | `#0f172a` | `#f1f5f9` |
| `--color-muted` | `#64748b` | `#94a3b8` |
| `--color-sidebar` | `#0B2A4A` | `#0a1f38` |
| `--color-sidebar-fg` | `#cbd5e1` | `#cbd5e1` |
| `--color-accent` | `#2E6DF0` | `#2E6DF0` |

Existing `brand-navy/blue/sky` tokens are retained for back-compat.

### Theme module (`src/theme.ts`) + `ThemeToggle`
- `getTheme()`, `setTheme('light'|'dark')`, `toggleTheme()` — read/write
  `localStorage['capex-theme']` and toggle `.dark` on `<html>`.
- An inline snippet applied before React renders (in `index.html` head or top of
  `main.tsx`) sets the class from storage to avoid a flash of wrong theme.
- `ThemeToggle` button (sun/moon lucide icon) lives in the header.

### Shell (`src/components/AppShell.tsx`)
- **Sidebar** (`bg-sidebar`): text lockup "United Uptime Services / CAPEX
  Tracking" at top; grouped nav with uppercase section headers and a lucide icon
  per item. Active item = solid blue pill. Sections:
  - OVERVIEW — Dashboard, New Request, My Requests
  - ADMIN (ADMIN role only) — Users, Divisions, Approval Thresholds
  - ACCOUNT — My Profile
- **Header:** left = page context ("Data last updated <date>"); right = user
  name, `ThemeToggle`, Sign Out (secondary pill).

Nav config becomes grouped (`{ section, items: [...] }`), role-filtered as today.

### Shared UI primitives (`src/components/ui/`)
- `Card.tsx` — `Card` (surface, rounded, border+shadow) and `StatCard`
  (uppercase muted label, big bold value, small sub-line).
- `Badge.tsx` — status pill; color map: DRAFT=slate, PENDING_*=amber/blue,
  APPROVED=green, REJECTED=red.
- `Button.tsx` — add `variant` prop: `primary` (default) / `secondary` / `ghost`.
- `Input.tsx`, `Select.tsx` — swap to token colors; dark-aware.

### Pages
- **Dashboard:** StatCard row — Pending My Approval, My Open Requests,
  Total CAPEX $ (my requests), Approved — computed from `listRequests`
  (`assigned` + `mine`). Below: approvals table in a Card with status Badges.
- **RequestsListPage / RequestsTable:** styled segmented scope control, Card-
  wrapped table, status Badges, accent links.
- **New Request, Request Detail, Wizard, Admin (Users/Divisions/Thresholds +
  forms), Profile, Login:** migrate `slate-*`/`brand-*` usages to semantic
  tokens; wrap major content in `Card` where it fits. Mostly mechanical.

## Verification / success criteria

1. `npm run typecheck` and `npm run build` pass.
2. `npm test` (vitest) passes — existing tests unaffected.
3. App runs; sidebar shows grouped nav with icons + active blue pill; header has
   working Sign Out.
4. Theme toggle flips light/dark across all pages and persists on reload with no
   flash.
5. Dashboard shows KPI StatCards + styled table with status badges.
6. Spot-check each route renders correctly in both themes.

## Out of scope

Backend changes, charts, new data/endpoints, logo mark/favicon, typography
changes (no IBM Plex).
