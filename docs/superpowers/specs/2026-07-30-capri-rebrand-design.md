# CAPEX Flow → CAPRI rebrand

**Date:** 2026-07-30
**Status:** approved, implementing

Rename the product from **CAPEX Flow** to **CAPRI** — *Capital Approval,
Planning, Reporting & Investment* — and adopt the refreshed brand bundle
(`brand/project/`, logo direction **1d "Capital Cycle"**).

## Scope decisions

Confirmed with Bryan before implementation:

1. **Depth:** brand-facing strings plus the cheap internal renames. No schema
   migration.
2. **Tagline placement:** the expansion appears on the login card *and* baked
   into the email header band. Nowhere else.
3. **Wordmark:** two-tone `CAP` + `RI`, using the existing font stacks — no new
   webfont. (Brand sets Archivo 800; the app keeps its system stack on the web
   and Arial Bold in the PNG.)

## Out of scope — and why

`CAPEX` remains the correct domain term: a request still *is* a capital
expenditure request. So these keep their names:

- `CapexRequest` model, `capex_requests` table, all `cost_*`/request columns
- `backend/instance/capex_dev.db`
- request numbering `CX000001…`
- the repo folder `capex_tracking` and the `capex_workflow` git remote

Also untouched:

- `CAPEX Flow - Proposed Enhancements.docx` — already circulated to Finance.
  The rename is noted inside `PHASE2-PROPOSALS.md` instead.
- `BrandMark.tsx` — unwired dead code; comment updated, code left alone.
- `backend/app/assets/email_logo.png` — pre-existing unused asset, not in
  `ASSET_FILES`. Left as-is.

## 1. Name and lockup

Hierarchy is unchanged. The new brand bundle's own sidebar mock
(`brand/project/UUS CAPEX Flow - Nav Icons.dc.html:123`) keeps **United Uptime
Services** as the dominant line with **CAPRI** secondary — exactly the
structure already shipped, so no layout restructuring.

The wordmark splits colour mid-word:

| Surface | `CAP` | `RI` |
| --- | --- | --- |
| Navy — sidebar, email band, editor replica | white | `brand-sky` `#93BBF5` |
| Light — login card, brand cards | `brand-navy` `#0B2A4A` | `brand-blue` `#2563EB` |

**Deliberate deviation:** the brand file uses `#5B9BFF` for `RI` on navy. We
reuse the existing `brand-sky` token rather than add a fourth blue to the
palette for a two-letter accent.

### `components/Wordmark.tsx`

A single component owns the split so the rule is not copy-pasted:

```tsx
Wordmark({ tone }: { tone: 'dark' | 'light' })
```

`dark` → white + `text-brand-sky`. `light` → `text-brand-navy` +
`text-brand-blue`. Consumers: `AppShell`, `LoginPage`, and the
`EmailTemplateEditor` header replica.

## 2. Logo mark — realigned to 1d

The shipped `Logo.tsx` had **drifted from brand direction 1d**. Brand 1d draws
the chevron pointing *up* (capital rising); the app drew it pointing *left*, so
the mark read as a back-arrow "‹" — visible in the shipped email header PNG.
The arrowhead wedge differed too.

`Logo.tsx` and `public/favicon.svg` are re-expressed on the brand's real
geometry (`viewBox="0 0 100 100"`):

```
arc:       M74 28 A33 33 0 1 0 82 54    stroke-width 11, round cap
arrowhead: polygon 63,20 84,20 74,38
chevron:   polyline 38,56 50,44 62,56   stroke-width 11, round cap+join
```

Colours per surface, matching the brand lockups: on navy the arc/arrowhead are
sky and the chevron white; on light surfaces the arc/arrowhead are `#2563EB`
and the chevron navy. The `tile` prop keeps rendering the navy rounded square.

This changes how the icon looks. It is intentional — it is what selecting 1d
means.

## 3. Email chrome

`email_header.png` has the wordmark rasterised into it (classic Outlook cannot
round CSS corners), so it must be regenerated.

### New generator: `backend/tools/gen_email_assets.py`

The current PNGs have **no generator** — only a reference sketch in
`email-rounded-corners-guide.md` §4. A committed Pillow script now owns them so
the next rebrand is not archaeology.

- Draws at 2× and downsamples; top corners rounded only on the header, bottom
  corners only on the closing strip.
- Rasterises the corrected 1d mark from the geometry above.
- Header grows **640×85 → 640×100** to fit the tagline line:

```
┌──────────────────────────────────────────────────┐
│  (mark)  United Uptime Services                  │
│          CAPRI                                   │
│          Capital Approval, Planning, Reporting…   │
└──────────────────────────────────────────────────┘
```

- **Buttons are not regenerated.** The script can produce all six assets, but
  only the header changes, and leaving the four button PNGs byte-identical
  avoids re-verifying four Outlook renders.

### `email_frame.py`

- header `height` `85` → `100`
- `alt` → `United Uptime Services — CAPRI`
- footer → `Automated message from CAPRI — please do not reply.`
- `CID_PREFIX` `capexflow-` → `capri-`

### Editor replica

`EmailTemplateEditor.tsx` renders a CSS replica of the band for WYSIWYG
editing (the preview *iframe* separately uses the real PNGs as data-URIs). The
replica gets the two-tone wordmark and the tagline line, or the editor drifts
from what is actually sent.

## 4. Mechanical sweep

**Frontend:** `index.html` title · `AppShell` · `LoginPage` ·
`EmailTemplatesPage` subtitle · `index.css` palette comment · header comments
in `Logo`, `BrandMark`, `NavIcons`, `ActionIcons`.

**Backend:** `pdf_service` page footer · `config.py` host example
(`capexflow.` → `capri.`) · `email_outlook` temp-dir prefix.

**Launcher:** `Start CAPEX Flow.cmd` → `Start CAPRI.cmd` (via `git mv`), plus
the `run-app.ps1` banner and the README instruction.

**Docs:** `CLAUDE.md`, `docs/SOP.md` (including its description of the email
band), `PHASE2-PROPOSALS.md`, `.claude/skills/verify/SKILL.md`, `README.md`,
`BID-APP-STARTER-GUIDE.md`, `email-rounded-corners-guide.md`.

**Brand folder:** commit the new bundle. The assets moved
`brand/*.html` → `brand/project/*.html`, which **breaks path references** in
`NavIcons.tsx`, `ActionIcons.tsx`, and `CLAUDE.md`; those are corrected. The
bundle keeps its delivered filenames (they still read "UUS CAPEX Flow" even
though the contents say CAPRI) — it is a vendor handoff, and renaming its files
would break its own README's internal paths.

Verified by diff against the previous bundle: the new assets are a **pure
wordmark swap**. The 1d geometry, the palette, and every nav/action icon are
byte-identical to what already ships, so there is no icon work.

## 5. Tests

- `test_email_templates.py`: three `cid:capexflow-*` assertions → `capri-`.
- Add one assertion pinning `CAPRI` and the tagline in the rendered frame.
- Existing `"United Uptime Services"` assertions still hold (the alt text keeps
  the company name), so `test_notify.py` needs no change.

## Revisions after review

Bryan reviewed the first implementation and asked for two changes, both applied:

1. **Sidebar and login use the brand's dark lockup** (`brand/capri-dark-lockup.png`)
   instead of the "United Uptime Services / CAPRI" stack: the mark beside a
   letterspaced `UUS` over the two-tone wordmark, **left-justified** as in the
   artwork. Extracted into `components/Lockup.tsx`; the login card wraps it in
   the navy `panel` from the artwork. This also settles the accent question in
   §1 the other way — the artwork uses `#5B9BFF`, so that is now a real token,
   `--color-brand-accent`, and `RI` on navy uses it.
   The **email band is unchanged** — he approved it as sent, so it keeps the
   full company name, the tagline, and the duller `#93BBF5` mark. `Logo` gained
   an `accent` prop so the email-template editor's replica can stay faithful to
   the PNG while the app lockup uses the brighter tone.
2. **Port moved 5000 -> 5100.** Ports 5000, 5040 and 5050 are taken by another
   app on Bryan's machine. Changed in `run-app.ps1` (both the `flask run
   --port` invocation and the health poll), `config.py`'s `APP_BASE_URL`
   default — which every email deep link is built from — the sample-context
   link, the verify skill, and the READMEs/SOP/CLAUDE.md.

## 6. Verification

1. `cd backend && pytest -q` — 236 tests.
2. `node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`
3. `node ./node_modules/vitest/vitest.mjs run`
4. `node ./node_modules/vite/bin/vite.js build`
5. Send a `[SAMPLE v1]` notification to Bryan for the **classic Outlook**
   check — a browser preview will not reveal whether the taller 100px band
   renders correctly.
6. `grep -ri "capex flow"` — only intended historical mentions should survive.
