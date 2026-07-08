# CAPEX Tracking — United Uptime Services

Capital expenditure request tracking and approval workflow. Replaces ContinuFlow.

## Dev setup

```bash
npm install
npx prisma db push   # creates dev.db (SQLite)
npm run seed         # admin / ChangeMe123!
npm run dev          # http://localhost:3000
```

## Tests

```bash
npm test
```

Tests run against `test.db` (SQLite), reset automatically.

## Databases

- Dev: SQLite (`prisma/dev.db`)
- Test/Prod: Azure SQL Server — swap `provider` in `prisma/schema.prisma` to
  `"sqlserver"` and set `DATABASE_URL` at deploy time (Phase 3).
- Prisma is pinned to `6.14` (`prisma` and `@prisma/client`) — do not upgrade:
  6.15+ adds an AI-agent consent gate, and v7 requires driver adapters.

## Structure

- `src/lib/` — business logic (unit-tested services)
- `src/app/` — routes: `/login`, `/profile`, `/admin/*` (Phase 1);
  `/requests/*` (Phase 2); dashboards & workflow (Phase 3)
