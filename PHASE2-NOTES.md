# Phase 2 — carried-over items from Phase 1 review

Deferred, non-blocking items surfaced by the Phase 1 whole-branch review. Address these during Phase 2 (request wizard, drafts, attachments, detail page).

## Do early in Phase 2
- **Shared zod validation layer.** Design §8 mandates server-side zod schemas shared with client forms. Phase 1 uses manual length/uniqueness checks only (email format and empty-after-trim fields are unvalidated). Stand up a `src/lib/validation/` module as the first Phase 2 task so the request wizard doesn't inherit ad-hoc `String(formData.get(...))` parsing.
- **Verify the schema against a real Azure SQL Server instance.** Phase 1 added FK referential actions (`onUpdate: NoAction`, and `onDelete: NoAction` on all User/Division-referencing FKs) to avoid SQL Server cascade-cycle/multiple-path errors, but this was only verified against SQLite. Do a one-time `provider="sqlserver"` + `prisma db push` dry-run against a throwaway SQL Server/Azure instance to confirm the DDL is accepted. Also confirm the lowercase-normalization (case-insensitive parity) behaves as intended there.

## Schema affordances (cheap to add while tables are empty)
- **`pendingSince` / `assignedAt` on `CapexRequest`.** The Phase 3 reminder job ("pending > N days", design §7) currently has no dedicated timestamp; `updatedAt` moves on any edit. Derivable from the latest `ApprovalAction.createdAt`, but an explicit column simplifies the reminder query.

## Hardening (Phase 2/3)
- **Last-admin / self-lockout guard** in `updateUser`: prevent an admin from removing their own ADMIN role or deactivating the only remaining admin.
- **`requireRole` returns 403/redirect, not a raw 500.** `src/lib/authz.ts` throws a plain `Error` on missing role; a non-admin reaching an admin route gets a 500 page. Nav already hides the links, so this is UX-only.
- **Login username-enumeration timing.** `authenticate` returns before any bcrypt compare for unknown users, so response timing reveals whether a username exists. Add a dummy `bcrypt.compare` against a constant hash to equalize timing.

## Minor / optional
- Move `ServiceResult` from `src/lib/user-service.ts` to its own `src/lib/service-result.ts` (division-service and threshold-service import it from user-service today — odd dependency direction).
