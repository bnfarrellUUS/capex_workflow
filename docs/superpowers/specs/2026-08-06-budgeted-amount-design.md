# Budgeted amount — design

**Date:** 2026-08-06
**Status:** approved, building

## Problem

`budgeted` is a bare yes/no flag in the wizard's Basic Info step. "Yes, this is
budgeted" tells an approver nothing about *how much* was budgeted, so there is
no way to see on the request whether the ask matches the plan. Approvers who
want that number have to go outside the app for it.

## Solution

When the requestor checks **Budgeted**, a **Budget amount** field appears
directly below the flags and must be filled in before they can leave the Basic
Info step. Unchecking the box hides the field and clears the stored amount.

Explicitly **not** in scope: comparing the budget amount to the request total,
budget rollups by division or year, warnings when the ask exceeds the budget.
Those belong to Phase 2 proposal #1 (budget tracking) in `PHASE2-PROPOSALS.md`,
which is still on hold for Finance.

## Data model

One new nullable column on `CapexRequest`, immediately after `budgeted`, plus
one Alembic migration:

| column | type | notes |
| --- | --- | --- |
| `budget_amount` | `MONEY` (`Numeric(18,2)`) | nullable, like every other optional dollar field |

Existing rows read as null. Null means "no amount recorded"; with
`budgeted=False` it means "not budgeted".

The column is **derived from the flag, not independent of it**: an unbudgeted
request always stores null (see "Clearing on uncheck"). Anything reading
`budget_amount` can therefore trust it without also checking `budgeted`.

## Threading the field through

Per the five-place rule in `CLAUDE.md`, a new editable request field must be
added in the model, the `request_out` serializer, the `RequestDraft` schema, the
frontend types, and `toForm`/`toPayload`:

| place | change |
| --- | --- |
| `models/__init__.py` | the column above |
| `services/request_service.py` (`request_out`) | `"budget_amount": money_str(req.budget_amount)` |
| `schemas/request.py` (`RequestDraft`) | `budget_amount: Decimal \| None = Field(None, ge=0)` |
| `api/requests.ts` (`CapexRequestData`) | `budget_amount: string \| null` |
| `routes/wizard/types.ts` | `budget_amount: string` on `RequestForm`; `''` in `blankForm`; `r.budget_amount ?? ''` in `toForm`; see `toPayload` below |

The `ge=0` bound is a **type-level constraint, not a raising
`field_validator`** — a validator that raises trips the app-wide
`ValidationError` handler bug and returns 500 instead of 400 (see "Known bug"
in `CLAUDE.md`).

## Input tolerance and normalization

The field accepts what the finance cost inputs accept: an optional `$`, commas,
and surrounding whitespace. `toPayload` strips those before sending, because
Pydantic's `Decimal` will not parse `$50,000`.

    // routes/wizard/types.ts
    const AMOUNT = (s: string) => {
      const t = s.replace(/[$,\s]/g, '')
      return t === '' ? null : t
    }

## Clearing on uncheck

`toPayload` sends the amount **only when the flag is set**:

    budget_amount: f.budgeted ? AMOUNT(f.budget_amount) : null,

`request_service.update_draft` applies the payload with a plain `setattr` loop,
so the null writes straight through and the column is cleared on the next save.
An unbudgeted request can never carry a stale figure into the detail page, the
record PDF, or the xlsx export.

The consequence, accepted: unchecking and re-checking the box means retyping the
number. The form keeps the typed text in memory during the session, but any save
in the unchecked state discards it.

## Validation

New `frontend/src/routes/wizard/validate.ts`:

    export function budgetAmountError(form: RequestForm): string | null

| condition | result |
| --- | --- |
| `!form.budgeted` | `null` |
| amount blank (after trimming) | `'Enter the budgeted amount.'` |
| not a number, or ≤ 0 | `'Enter a valid dollar amount.'` |
| otherwise | `null` |

A separate module rather than a helper in `types.ts`: `types.ts` owns the
API↔form mapping, and this is a pure predicate over `RequestForm` that is worth
unit-testing on its own.

### Where it gates

`WizardPage.goToStep` — the handler behind both **Next** and the stepper tabs —
calls `budgetAmountError` when the current step is `basic_info`. On an error it
stores the message in state and returns without advancing.

- **Save Draft never calls it.** A half-finished request must always be
  saveable; the wizard holds the form in memory until a save, so refusing to
  save would lose the session's work if the user walked away.
- **Back needs no guard.** Basic Info is always step 0 (it is not hideable), so
  Back is already disabled there and cannot leave the step.
- The gate is not escapable: Review — and therefore Submit — lives past step 0,
  so it cannot be reached without a valid amount.

### Server-side backstop

One check in `workflow_service._open_workflow`, beside the existing line-item
and division checks:

    if req.budgeted and (req.budget_amount is None or req.budget_amount <= 0):
        raise ServiceError("Enter the budgeted amount for this request.")

`_open_workflow` is shared by submit and resubmit, so this covers a REJECTED
request being resubmitted and any direct API call. The requirement is a rule of
the workflow, not just a convention of the wizard.

## UI

**Wizard, Basic Info step.** A conditional `Field label="Budget amount"` block
after the Flags `<fieldset>`, rendered only when `form.budgeted`, with a caption
noting it is required because the request is flagged as budgeted, and the
validation message below the input when present.

Rejected alternative: indenting the input inside the Flags grid under the
Budgeted checkbox. `FLAGS` renders as a two-column `.map`; injecting an input
into one cell stretches that grid row and misaligns the pairs below it, and it
means branching inside the map. A separate field block also matches the styling
of Date / Description / Division and leaves room for the error text.

**Three read-only spots**, each showing the value only when `budgeted` is true:

| place | change |
| --- | --- |
| `RequestDetailPage` `FullDetails` | a "Budget amount" cell in the Basic-info grid |
| `pdf_service.request_pdf_sections` | `("Budget amount", _money(req.budget_amount))` appended to the Basic info fields |
| `export_service._COLUMNS` | a `"Budget Amount"` money column right after `Budgeted` |

The wizard's Review step is unchanged — it summarizes description, line-item
count, total, and attachments, not the flags.

## Testing

**Backend**

- `RequestDraft` accepts `budget_amount`, rejects a negative value with 400.
- `PATCH` persists the amount; sending null clears an existing amount.
- Submit and resubmit are rejected when `budgeted` is set with no amount (or 0),
  and succeed once an amount is present.
- `request_out` carries `budget_amount`.
- `request_pdf_sections` includes the row when budgeted, omits it otherwise.
- The export has the column.

**Frontend**

- `validate.ts` unit tests for each row of the table above.
- `WizardPage`: checking Budgeted reveals the field; Next is blocked with the
  error message and the step does not change; entering an amount lets Next
  advance; Save Draft succeeds with the amount blank.
- `toPayload` strips `$` and commas, and sends null when the flag is off.
