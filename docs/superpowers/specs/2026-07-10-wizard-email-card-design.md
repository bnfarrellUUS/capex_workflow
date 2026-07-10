# Design: Wizard "email card" restyle

**Date:** 2026-07-10 · **Status:** Approved (option A)

Restyle the New Request wizard (`frontend/src/routes/WizardPage.tsx`) to match
the notification-email look: one rounded card with a navy `#0B2A4A` header band
(Capital-Cycle `Logo` + white "Request CX…" title + sky `#93BBF5`
"New Capital Request" subtitle), a numbered stepper on a light band beneath it
(✓ for completed, accent for active, muted for upcoming — same click-to-jump
save-then-navigate behavior), the form content with the email body's padding,
and a footer bar inside the card (hairline top border) holding
Back / Save Draft / status / Next. Flags become a two-column grid.

Style-only: no logic, field, routing, or API changes. Semantic tokens keep dark
mode working (the navy band is constant, like the email). Verify with
typecheck + vitest + build and a before/after screenshot in the running app.
