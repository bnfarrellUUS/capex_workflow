# CAPEX Tracking — Phase 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the CAPEX tracking app skeleton: Next.js project, full database schema, username/password login with lockout, role-aware app shell, and the admin panel (users, divisions, approval thresholds).

**Architecture:** Single Next.js 15 (App Router) deployment: React server components + server actions, Prisma ORM against SQLite in dev (Azure SQL Server in test/prod later). Auth.js (next-auth v5) credentials provider with JWT sessions; middleware guards all routes. Business logic lives in `src/lib/*` service modules that are unit-tested with Vitest against a real SQLite test database.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, Prisma, next-auth v5 (beta), bcryptjs, zod, Vitest.

## Global Constraints

- Company name in all UI/copy: **United Uptime Services** (never "D&H United").
- Database schema must work identically on SQLite and SQL Server: **no DB enums, no arrays, no provider-specific native types**. Statuses/roles stored as strings validated in app code.
- Money fields use Prisma `Decimal`.
- Passwords hashed with **bcryptjs** (pure JS — no native builds).
- All authorization checks happen **server-side** in server actions/route handlers (`requireRole`), never only in the UI.
- Request statuses: `DRAFT → SUBMITTED → PENDING_L1 → PENDING_L2 → PENDING_L3 → APPROVED | REJECTED`.
- Roles: `REQUESTOR`, `APPROVER`, `FINANCE`, `ADMIN` (a user may hold several).
- App code lives in `capex-app/` inside the repo root `capex_tracking/`.
- Login lockout: 5 consecutive failures locks the account for 15 minutes.
- App Router conventions: Next 15 async `params`/`cookies`. Path alias `@/*` → `capex-app/src/*`.
- Brand (from repo `brand/usage.html`): navy `#0B2A4A`, blue `#2E6DF0` (primary accent), sky `#8FB2FF` (accent on dark); typeface IBM Plex Sans; logo mark `brand/aria-mark.svg` (uses currentColor); favicon `brand/aria-favicon.svg`.
- **Light and dark mode both supported** via next-themes (class strategy), toggle in the header, defaults to system preference. Use semantic/theme-aware classes — never hard-code light-only colors in pages.

**Working directory note:** All commands below run from `capex-app/` unless stated otherwise. Repo root is `C:\Users\bryan.farrell\OneDrive - D&H United Fueling Solutions, Inc\claude_code\capex_tracking`.

---

### Task 1: Scaffold project, tooling, and git

**Files:**
- Create: `capex-app/` (via create-next-app), `.gitignore` (repo root), `capex-app/vitest.config.ts`, `capex-app/tests/smoke.test.ts`, `capex-app/src/app/icon.svg`, `capex-app/src/components/brand-logo.tsx`, `capex-app/src/components/theme-provider.tsx`, `capex-app/src/components/theme-toggle.tsx`
- Modify: `capex-app/package.json` (scripts), `capex-app/src/app/globals.css`, `capex-app/src/app/layout.tsx`

**Interfaces:**
- Produces: running Next.js app; `npm test` (Vitest); path alias `@/*` → `src/*`; shadcn/ui components in `src/components/ui/`; `<BrandLogo className>` and `<ThemeToggle>` components; Tailwind classes `bg-brand-navy`, `text-brand-blue`, `text-brand-sky`; light/dark theming via next-themes.

- [ ] **Step 1: Initialize git at repo root**

```bash
cd "C:\Users\bryan.farrell\OneDrive - D&H United Fueling Solutions, Inc\claude_code\capex_tracking"
git init
```

Create `.gitignore` at repo root:

```gitignore
node_modules/
.next/
*.db
*.db-journal
.env
.env.local
capex-app/uploads/
```

- [ ] **Step 2: Scaffold Next.js app**

```bash
npx create-next-app@15 capex-app --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-turbopack
cd capex-app
```

Expected: project created, `npm run dev` works (verify next step).

- [ ] **Step 3: Verify dev server boots**

Run: `npm run dev` — open http://localhost:3000, expect the Next.js welcome page. Stop the server.

- [ ] **Step 4: Install dependencies**

```bash
npm install @prisma/client next-auth@beta bcryptjs zod next-themes
npm install -D prisma vitest tsx
```

- [ ] **Step 5: Initialize shadcn/ui and add base components**

```bash
npx shadcn@latest init -d
npx shadcn@latest add button input label card table select checkbox badge
```

Expected: components appear under `src/components/ui/`.

- [ ] **Step 6: Brand theme, fonts, favicon, and dark mode scaffolding**

Copy the brand favicon (run from `capex-app/`; Next.js serves `src/app/icon.svg` as the favicon automatically):

```bash
cp "../brand/aria-favicon.svg" src/app/icon.svg
```

Append brand colors to `src/app/globals.css`:

```css
@theme {
  --color-brand-navy: #0B2A4A;
  --color-brand-blue: #2E6DF0;
  --color-brand-sky: #8FB2FF;
}
```

In the same file, override the shadcn primary tokens: in the existing `:root` block set `--primary: #2E6DF0;` and `--primary-foreground: #ffffff;`; in the existing `.dark` block set `--primary: #8FB2FF;` and `--primary-foreground: #0B2A4A;`.

Create `src/components/brand-logo.tsx` (inline SVG from `brand/aria-mark.svg` — currentColor adapts to theme):

```tsx
export function BrandLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" fill="none" aria-hidden="true" className={className}>
      <path d="M15 44 L32 16 L49 44" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M22 35 L42 35" stroke="currentColor" strokeWidth="5" strokeLinecap="round" />
      <path d="M11 55 Q37 60 54 37" stroke="currentColor" strokeWidth="4" fill="none" strokeLinecap="round" opacity="0.42" />
    </svg>
  );
}
```

Create `src/components/theme-provider.tsx`:

```tsx
"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      {children}
    </NextThemesProvider>
  );
}
```

Create `src/components/theme-toggle.tsx`:

```tsx
"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Toggle theme"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    >
      <Sun className="h-4 w-4 dark:hidden" />
      <Moon className="hidden h-4 w-4 dark:block" />
    </Button>
  );
}
```

Replace `src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

const plexSans = IBM_Plex_Sans({ subsets: ["latin"], weight: ["400", "600", "700"] });

export const metadata: Metadata = {
  title: "CAPEX Tracking — United Uptime Services",
  description: "Capital expenditure request tracking and approval workflow",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={plexSans.className}>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
```

Verify: `npm run dev` — welcome page renders in IBM Plex Sans with the ARIA favicon in the browser tab.

- [ ] **Step 7: Configure Vitest**

Create `capex-app/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    globalSetup: "./tests/global-setup.ts",
    env: { DATABASE_URL: "file:./test.db" },
    fileParallelism: false, // one shared SQLite test db
  },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
```

Create placeholder `capex-app/tests/global-setup.ts` (fleshed out in Task 2):

```ts
export default function globalSetup() {}
```

Create `capex-app/tests/smoke.test.ts`:

```ts
import { describe, it, expect } from "vitest";

describe("smoke", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

Add to `capex-app/package.json` scripts:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 8: Run the smoke test**

Run: `npm test`
Expected: 1 passed.

- [ ] **Step 9: Commit**

```bash
cd ..
git add -A
git commit -m "chore: scaffold Next.js app with Tailwind, shadcn/ui, Vitest, brand theme"
```

---

### Task 2: Prisma schema, client singleton, test harness

**Files:**
- Create: `capex-app/prisma/schema.prisma`, `capex-app/.env`, `capex-app/src/lib/prisma.ts`, `capex-app/tests/helpers/db.ts`
- Modify: `capex-app/tests/global-setup.ts`, `capex-app/package.json`
- Test: `capex-app/tests/schema.test.ts`

**Interfaces:**
- Produces: `prisma` client singleton (`@/lib/prisma`); full DB schema (all models for all phases); `resetDb()` test helper.

- [ ] **Step 1: Create `.env`**

```env
DATABASE_URL="file:./dev.db"
AUTH_SECRET="dev-secret-change-in-production"
```

- [ ] **Step 2: Write the full schema**

Create `capex-app/prisma/schema.prisma`:

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "sqlite" // swapped to "sqlserver" for test/prod deployment
  url      = env("DATABASE_URL")
}

model User {
  id               String    @id @default(cuid())
  username         String    @unique
  email            String    @unique
  name             String
  passwordHash     String
  roles            String    @default("[\"REQUESTOR\"]") // JSON array of role strings
  active           Boolean   @default(true)
  divisionId       String?
  division         Division? @relation(fields: [divisionId], references: [id])
  delegateId       String?
  delegate         User?     @relation("Delegation", fields: [delegateId], references: [id])
  delegatesFor     User[]    @relation("Delegation")
  failedLogins     Int       @default(0)
  lockedUntil      DateTime?
  resetToken       String?   @unique
  resetTokenExpiry DateTime?
  createdAt        DateTime  @default(now())
  updatedAt        DateTime  @updatedAt

  requests         CapexRequest[]      @relation("Requestor")
  assignedRequests CapexRequest[]      @relation("Assignee")
  approvalActions  ApprovalAction[]
  attachments      Attachment[]
  l1ApproverFor    Division[]          @relation("L1Approver")
  levelApproverFor ApprovalThreshold[] @relation("LevelApprover")
}

model Division {
  id           String  @id @default(cuid())
  number       String  @unique
  name         String
  active       Boolean @default(true)
  l1ApproverId String?
  l1Approver   User?   @relation("L1Approver", fields: [l1ApproverId], references: [id])

  users    User[]
  requests CapexRequest[]
}

model ApprovalThreshold {
  id         String   @id @default(cuid())
  level      Int      @unique // 1, 2, 3
  maxAmount  Decimal? // requests up to this amount stop at this level; null = no limit (top level)
  approverId String?  // company-wide approver for levels 2 and 3; level 1 uses Division.l1Approver
  approver   User?    @relation("LevelApprover", fields: [approverId], references: [id])
}

model CapexRequest {
  id                String    @id @default(cuid())
  number            String    @unique // CX000001
  status            String    @default("DRAFT")
  requestorId       String
  requestor         User      @relation("Requestor", fields: [requestorId], references: [id])
  assigneeId        String?
  assignee          User?     @relation("Assignee", fields: [assigneeId], references: [id])
  divisionId        String?
  division          Division? @relation(fields: [divisionId], references: [id])
  requestDate       DateTime  @default(now())

  // Basic info
  description       String  @default("")
  budgeted          Boolean @default(false)
  replacement       Boolean @default(false)
  healthSafety      Boolean @default(false)
  revenueGenerating Boolean @default(false)
  environmental     Boolean @default(false)
  competitiveBids   Boolean @default(false)
  leaseRecommended  Boolean @default(false)

  // Narrative sections
  justification      String @default("")
  effectOnOperations String @default("")

  // Economic justification
  assetLife     String?
  irrAfterTax   Decimal?
  firstYearEbit Decimal?
  annualSavings Decimal?
  paybackYears  Decimal?
  npvSavings    Decimal?

  // Finance section (completed after final approval)
  costAutosTrucks  Decimal?
  costMachinery    Decimal?
  costImprovements Decimal?
  costFurniture    Decimal?
  costPermits      Decimal?
  costMisc         Decimal?
  financeCompleted Boolean @default(false)

  totalCost      Decimal @default(0)
  requiredLevels Int     @default(1)
  currentLevel   Int     @default(0)

  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  equipmentItems EquipmentItem[]
  attachments    Attachment[]
  actions        ApprovalAction[]
  notifications  NotificationLog[]
}

model EquipmentItem {
  id        String       @id @default(cuid())
  requestId String
  request   CapexRequest @relation(fields: [requestId], references: [id], onDelete: Cascade)
  units     Int
  condition String // "NEW" | "USED"
  type      String
  make      String
  model     String
  cost      Decimal
}

model Attachment {
  id           String       @id @default(cuid())
  requestId    String
  request      CapexRequest @relation(fields: [requestId], references: [id], onDelete: Cascade)
  filename     String
  storagePath  String
  contentType  String
  size         Int
  uploadedById String
  uploadedBy   User         @relation(fields: [uploadedById], references: [id])
  createdAt    DateTime     @default(now())
}

model ApprovalAction {
  id         String       @id @default(cuid())
  requestId  String
  request    CapexRequest @relation(fields: [requestId], references: [id], onDelete: Cascade)
  actorId    String
  actor      User         @relation(fields: [actorId], references: [id])
  actedForId String? // set when actor acted as a delegate for this user id
  action     String // SUBMITTED | APPROVED | REJECTED | RESUBMITTED | FINANCE_COMPLETED
  level      Int?
  comment    String?
  createdAt  DateTime     @default(now())
}

model NotificationLog {
  id        String        @id @default(cuid())
  requestId String?
  request   CapexRequest? @relation(fields: [requestId], references: [id], onDelete: SetNull)
  recipient String
  type      String // ASSIGNED | DECIDED | FINANCE_READY | REMINDER
  sentAt    DateTime      @default(now())
}

model Counter {
  name  String @id
  value Int
}

model AppSetting {
  key   String @id
  value String
}
```

- [ ] **Step 3: Create dev database**

```bash
npx prisma db push
```

Expected: "Your database is now in sync with your Prisma schema." and generated client.

- [ ] **Step 4: Prisma client singleton**

Create `capex-app/src/lib/prisma.ts`:

```ts
import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

export const prisma = globalForPrisma.prisma ?? new PrismaClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
```

- [ ] **Step 5: Test harness**

Replace `capex-app/tests/global-setup.ts`:

```ts
import { execSync } from "node:child_process";

export default function globalSetup() {
  execSync("npx prisma db push --force-reset --skip-generate", {
    env: { ...process.env, DATABASE_URL: "file:./test.db" },
    stdio: "inherit",
  });
}
```

Create `capex-app/tests/helpers/db.ts`:

```ts
import { prisma } from "@/lib/prisma";

/** Delete all rows in FK-safe order. Call in beforeEach. */
export async function resetDb() {
  await prisma.notificationLog.deleteMany();
  await prisma.approvalAction.deleteMany();
  await prisma.attachment.deleteMany();
  await prisma.equipmentItem.deleteMany();
  await prisma.capexRequest.deleteMany();
  await prisma.approvalThreshold.deleteMany();
  await prisma.user.updateMany({ data: { delegateId: null } });
  await prisma.division.updateMany({ data: { l1ApproverId: null } });
  await prisma.user.deleteMany();
  await prisma.division.deleteMany();
  await prisma.counter.deleteMany();
  await prisma.appSetting.deleteMany();
}
```

- [ ] **Step 6: Write schema round-trip test**

Create `capex-app/tests/schema.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";

describe("schema", () => {
  beforeEach(resetDb);

  it("creates and reads a user with a division", async () => {
    const division = await prisma.division.create({
      data: { number: "100", name: "Humble/Houston" },
    });
    const user = await prisma.user.create({
      data: {
        username: "jdoe",
        email: "jdoe@uniteduptime.com",
        name: "Jane Doe",
        passwordHash: "x",
        roles: '["REQUESTOR"]',
        divisionId: division.id,
      },
    });
    const found = await prisma.user.findUnique({
      where: { username: "jdoe" },
      include: { division: true },
    });
    expect(found?.email).toBe("jdoe@uniteduptime.com");
    expect(found?.division?.name).toBe("Humble/Houston");
    expect(found?.id).toBe(user.id);
  });
});
```

- [ ] **Step 7: Run tests**

Run: `npm test`
Expected: schema test + smoke test pass.

- [ ] **Step 8: Commit**

```bash
cd ..
git add -A
git commit -m "feat: full Prisma schema, client singleton, test harness"
```

---

### Task 3: Roles helpers and auth service (hashing, authenticate, lockout)

**Files:**
- Create: `capex-app/src/lib/roles.ts`, `capex-app/src/lib/auth-service.ts`
- Test: `capex-app/tests/auth-service.test.ts`

**Interfaces:**
- Produces:
  - `ROLES: readonly ["REQUESTOR","APPROVER","FINANCE","ADMIN"]`, `type Role`, `parseRoles(json: string): Role[]`, `serializeRoles(roles: Role[]): string` from `@/lib/roles`
  - `hashPassword(plain: string): Promise<string>`, `verifyPassword(plain: string, hash: string): Promise<boolean>`, `authenticate(username: string, password: string): Promise<User | null>` from `@/lib/auth-service`
- Consumes: `prisma` from Task 2.

- [ ] **Step 1: Write failing tests**

Create `capex-app/tests/auth-service.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";
import { hashPassword, verifyPassword, authenticate } from "@/lib/auth-service";
import { parseRoles, serializeRoles } from "@/lib/roles";

async function makeUser(overrides: Record<string, unknown> = {}) {
  return prisma.user.create({
    data: {
      username: "jdoe",
      email: "jdoe@uniteduptime.com",
      name: "Jane Doe",
      passwordHash: await hashPassword("CorrectHorse1!"),
      roles: '["REQUESTOR"]',
      ...overrides,
    },
  });
}

describe("roles helpers", () => {
  it("round-trips roles", () => {
    expect(parseRoles(serializeRoles(["ADMIN", "APPROVER"]))).toEqual(["ADMIN", "APPROVER"]);
  });
  it("rejects unknown roles", () => {
    expect(() => parseRoles('["SUPERUSER"]')).toThrow();
  });
});

describe("password hashing", () => {
  it("verifies a correct password and rejects a wrong one", async () => {
    const hash = await hashPassword("s3cret!");
    expect(await verifyPassword("s3cret!", hash)).toBe(true);
    expect(await verifyPassword("nope", hash)).toBe(false);
  });
});

describe("authenticate", () => {
  beforeEach(resetDb);

  it("returns the user for valid credentials", async () => {
    await makeUser();
    const user = await authenticate("jdoe", "CorrectHorse1!");
    expect(user?.username).toBe("jdoe");
  });

  it("returns null for a wrong password and increments failedLogins", async () => {
    await makeUser();
    expect(await authenticate("jdoe", "wrong")).toBeNull();
    const u = await prisma.user.findUnique({ where: { username: "jdoe" } });
    expect(u?.failedLogins).toBe(1);
  });

  it("returns null for unknown user and inactive user", async () => {
    expect(await authenticate("ghost", "x")).toBeNull();
    await makeUser({ active: false });
    expect(await authenticate("jdoe", "CorrectHorse1!")).toBeNull();
  });

  it("locks the account after 5 failures", async () => {
    await makeUser();
    for (let i = 0; i < 5; i++) await authenticate("jdoe", "wrong");
    const u = await prisma.user.findUnique({ where: { username: "jdoe" } });
    expect(u?.lockedUntil).not.toBeNull();
    // correct password still rejected while locked
    expect(await authenticate("jdoe", "CorrectHorse1!")).toBeNull();
  });

  it("resets failure count on success", async () => {
    await makeUser();
    await authenticate("jdoe", "wrong");
    await authenticate("jdoe", "CorrectHorse1!");
    const u = await prisma.user.findUnique({ where: { username: "jdoe" } });
    expect(u?.failedLogins).toBe(0);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — cannot resolve `@/lib/auth-service` / `@/lib/roles`.

- [ ] **Step 3: Implement roles helpers**

Create `capex-app/src/lib/roles.ts`:

```ts
export const ROLES = ["REQUESTOR", "APPROVER", "FINANCE", "ADMIN"] as const;
export type Role = (typeof ROLES)[number];

export function parseRoles(json: string): Role[] {
  const parsed: unknown = JSON.parse(json);
  if (!Array.isArray(parsed)) throw new Error("roles must be a JSON array");
  for (const r of parsed) {
    if (!ROLES.includes(r as Role)) throw new Error(`Unknown role: ${String(r)}`);
  }
  return parsed as Role[];
}

export function serializeRoles(roles: Role[]): string {
  return JSON.stringify(roles);
}
```

- [ ] **Step 4: Implement auth service**

Create `capex-app/src/lib/auth-service.ts`:

```ts
import bcrypt from "bcryptjs";
import type { User } from "@prisma/client";
import { prisma } from "@/lib/prisma";

const MAX_FAILURES = 5;
const LOCKOUT_MINUTES = 15;

export async function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, 10);
}

export async function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}

/**
 * Validates credentials. Returns the user on success, null on any failure
 * (unknown user, inactive, locked, or bad password). Applies lockout:
 * 5 consecutive failures locks the account for 15 minutes.
 */
export async function authenticate(username: string, password: string): Promise<User | null> {
  const user = await prisma.user.findUnique({ where: { username } });
  if (!user || !user.active) return null;
  if (user.lockedUntil && user.lockedUntil > new Date()) return null;

  const ok = await verifyPassword(password, user.passwordHash);
  if (!ok) {
    const failures = user.failedLogins + 1;
    await prisma.user.update({
      where: { id: user.id },
      data: {
        failedLogins: failures,
        lockedUntil:
          failures >= MAX_FAILURES
            ? new Date(Date.now() + LOCKOUT_MINUTES * 60_000)
            : null,
      },
    });
    return null;
  }

  if (user.failedLogins > 0 || user.lockedUntil) {
    await prisma.user.update({
      where: { id: user.id },
      data: { failedLogins: 0, lockedUntil: null },
    });
  }
  return user;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd ..
git add -A
git commit -m "feat: roles helpers and auth service with lockout (TDD)"
```

---

### Task 4: Seed script

**Files:**
- Create: `capex-app/prisma/seed.ts`
- Modify: `capex-app/package.json`

**Interfaces:**
- Consumes: `hashPassword`, `serializeRoles`.
- Produces: seeded admin user (`admin` / `ChangeMe123!`), sample divisions, 3 threshold rows (L1 ≤ $10,000; L2 ≤ $50,000; L3 unlimited).

- [ ] **Step 1: Write the seed script**

Create `capex-app/prisma/seed.ts`:

```ts
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const passwordHash = await bcrypt.hash("ChangeMe123!", 10);

  const admin = await prisma.user.upsert({
    where: { username: "admin" },
    update: {},
    create: {
      username: "admin",
      email: "capex-admin@uniteduptime.com",
      name: "System Administrator",
      passwordHash,
      roles: '["ADMIN","REQUESTOR"]',
    },
  });

  await prisma.division.upsert({
    where: { number: "100" },
    update: {},
    create: { number: "100", name: "Humble/Houston" },
  });

  for (const t of [
    { level: 1, maxAmount: "10000" },
    { level: 2, maxAmount: "50000" },
    { level: 3, maxAmount: null },
  ]) {
    await prisma.approvalThreshold.upsert({
      where: { level: t.level },
      update: {},
      create: { level: t.level, maxAmount: t.maxAmount },
    });
  }

  await prisma.counter.upsert({
    where: { name: "capexNumber" },
    update: {},
    create: { name: "capexNumber", value: 0 },
  });

  console.log(`Seeded. Admin login: admin / ChangeMe123! (${admin.email})`);
}

main().finally(() => prisma.$disconnect());
```

Add to `capex-app/package.json` scripts:

```json
"seed": "tsx prisma/seed.ts"
```

- [ ] **Step 2: Run and verify**

Run: `npm run seed`
Expected output: `Seeded. Admin login: admin / ChangeMe123! ...`
Verify: `npx prisma studio` (optional) shows 1 user, 1 division, 3 thresholds. Running `npm run seed` a second time succeeds without duplicates (upserts).

- [ ] **Step 3: Commit**

```bash
cd ..
git add -A
git commit -m "feat: seed script (admin user, division, thresholds)"
```

---

### Task 5: Login flow — next-auth config, middleware, login page

**Files:**
- Create: `capex-app/src/auth.config.ts`, `capex-app/src/auth.ts`, `capex-app/src/app/api/auth/[...nextauth]/route.ts`, `capex-app/src/middleware.ts`, `capex-app/src/types/next-auth.d.ts`, `capex-app/src/app/login/page.tsx`, `capex-app/src/app/login/actions.ts`

**Interfaces:**
- Consumes: `authenticate`, `parseRoles`.
- Produces: `auth()` (session getter), `signIn`, `signOut` from `@/auth`. Session shape: `session.user = { id, name, email, roles: Role[], divisionId: string | null }`. All routes except `/login` and auth API require a session.

- [ ] **Step 1: Edge-safe auth config**

Create `capex-app/src/auth.config.ts`:

```ts
import type { NextAuthConfig } from "next-auth";

export const authConfig = {
  pages: { signIn: "/login" },
  session: { strategy: "jwt" },
  providers: [], // credentials provider added in auth.ts (needs Prisma, not edge-safe)
  callbacks: {
    authorized({ auth }) {
      return !!auth?.user; // middleware: signed-in users only
    },
    jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.roles = user.roles;
        token.divisionId = user.divisionId;
      }
      return token;
    },
    session({ session, token }) {
      session.user.id = token.id as string;
      session.user.roles = token.roles as string[];
      session.user.divisionId = token.divisionId as string | null;
      return session;
    },
  },
} satisfies NextAuthConfig;
```

- [ ] **Step 2: Full auth setup with credentials provider**

Create `capex-app/src/auth.ts`:

```ts
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "@/auth.config";
import { authenticate } from "@/lib/auth-service";
import { parseRoles } from "@/lib/roles";

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  providers: [
    Credentials({
      credentials: { username: {}, password: {} },
      async authorize(credentials) {
        const user = await authenticate(
          String(credentials?.username ?? ""),
          String(credentials?.password ?? "")
        );
        if (!user) return null;
        return {
          id: user.id,
          name: user.name,
          email: user.email,
          roles: parseRoles(user.roles),
          divisionId: user.divisionId,
        };
      },
    }),
  ],
});
```

Create `capex-app/src/types/next-auth.d.ts`:

```ts
import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface User {
    roles: string[];
    divisionId: string | null;
  }
  interface Session {
    user: {
      id: string;
      roles: string[];
      divisionId: string | null;
    } & DefaultSession["user"];
  }
}
```

Create `capex-app/src/app/api/auth/[...nextauth]/route.ts`:

```ts
import { handlers } from "@/auth";

export const { GET, POST } = handlers;
```

- [ ] **Step 3: Middleware**

Create `capex-app/src/middleware.ts`:

```ts
import NextAuth from "next-auth";
import { authConfig } from "@/auth.config";

export default NextAuth(authConfig).auth;

export const config = {
  matcher: ["/((?!api/auth|login|_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 4: Login server action**

Create `capex-app/src/app/login/actions.ts`:

```ts
"use server";

import { AuthError } from "next-auth";
import { signIn } from "@/auth";

export async function loginAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  try {
    await signIn("credentials", {
      username: formData.get("username"),
      password: formData.get("password"),
      redirectTo: "/",
    });
  } catch (error) {
    if (error instanceof AuthError) {
      return "Invalid username or password, or account is locked.";
    }
    throw error; // NEXT_REDIRECT on success must re-throw
  }
}
```

- [ ] **Step 5: Login page**

Create `capex-app/src/app/login/page.tsx`:

```tsx
"use client";

import { useActionState } from "react";
import { loginAction } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BrandLogo } from "@/components/brand-logo";

export default function LoginPage() {
  const [error, formAction, pending] = useActionState(loginAction, undefined);

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="flex flex-col items-center gap-2 text-center">
            <BrandLogo className="h-10 w-10 text-brand-navy dark:text-white" />
            <div className="text-xl font-bold">United Uptime Services</div>
            <div className="text-sm font-normal text-muted-foreground">
              CAPEX Tracking
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form action={formAction} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="username">Username</Label>
              <Input id="username" name="username" autoComplete="username" required />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input id="password" name="password" type="password" autoComplete="current-password" required />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
```

- [ ] **Step 6: Verify login end-to-end**

Run: `npm run dev`
- Visit http://localhost:3000 → expect redirect to `/login`.
- Sign in `admin` / `wrongpass` → error message shown.
- Sign in `admin` / `ChangeMe123!` → redirected to `/` (still the Next.js welcome page for now).
Also run `npm test` — expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd ..
git add -A
git commit -m "feat: username/password login with next-auth, middleware guard"
```

---

### Task 6: App shell — layout, role-based nav, dashboard placeholder

**Files:**
- Create: `capex-app/src/components/app-shell.tsx`, `capex-app/src/lib/authz.ts`
- Modify: `capex-app/src/app/page.tsx`

**Interfaces:**
- Consumes: `auth`, `signOut` from `@/auth`; `Role` from `@/lib/roles`.
- Produces: `requireSession(): Promise<Session>` and `requireRole(role: Role): Promise<Session>` from `@/lib/authz` (used by every later server action/page); `<AppShell session={session}>` layout component.

- [ ] **Step 1: Authorization helpers**

Create `capex-app/src/lib/authz.ts`:

```ts
import { redirect } from "next/navigation";
import type { Session } from "next-auth";
import { auth } from "@/auth";
import type { Role } from "@/lib/roles";

export async function requireSession(): Promise<Session> {
  const session = await auth();
  if (!session?.user) redirect("/login");
  return session;
}

export async function requireRole(role: Role): Promise<Session> {
  const session = await requireSession();
  if (!session.user.roles.includes(role)) {
    throw new Error("Forbidden: missing role " + role);
  }
  return session;
}
```

- [ ] **Step 2: App shell component**

Create `capex-app/src/components/app-shell.tsx`:

```tsx
import Link from "next/link";
import type { Session } from "next-auth";
import { signOut } from "@/auth";
import { Button } from "@/components/ui/button";
import { BrandLogo } from "@/components/brand-logo";
import { ThemeToggle } from "@/components/theme-toggle";

const NAV = [
  { href: "/", label: "Dashboard", roles: [] as string[] },
  { href: "/requests/new", label: "New Request", roles: ["REQUESTOR"] },
  { href: "/requests", label: "Search Requests", roles: [] as string[] },
  { href: "/requests/rejected", label: "My Rejected", roles: ["REQUESTOR"] },
  { href: "/admin/users", label: "Users", roles: ["ADMIN"] },
  { href: "/admin/divisions", label: "Divisions", roles: ["ADMIN"] },
  { href: "/admin/thresholds", label: "Approval Thresholds", roles: ["ADMIN"] },
  { href: "/profile", label: "My Profile", roles: [] as string[] },
];

export function AppShell({ session, children }: { session: Session; children: React.ReactNode }) {
  const roles = session.user.roles;
  const visible = NAV.filter((n) => n.roles.length === 0 || n.roles.some((r) => roles.includes(r)));

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 border-r bg-brand-navy text-white">
        <div className="flex items-center gap-3 border-b border-white/15 p-4">
          <BrandLogo className="h-8 w-8 shrink-0 text-white" />
          <div>
            <div className="font-bold leading-tight">United Uptime Services</div>
            <div className="text-xs text-brand-sky">CAPEX Tracking</div>
          </div>
        </div>
        <nav className="space-y-1 p-2">
          {visible.map((n) => (
            <Link key={n.href} href={n.href}
              className="block rounded px-3 py-2 text-sm hover:bg-card/10">
              {n.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-end gap-3 border-b bg-card px-6 py-3">
          <ThemeToggle />
          <span className="text-sm text-muted-foreground">{session.user.name}</span>
          <form action={async () => { "use server"; await signOut({ redirectTo: "/login" }); }}>
            <Button variant="outline" size="sm" type="submit">Sign out</Button>
          </form>
        </header>
        <main className="flex-1 bg-muted/40 p-6">{children}</main>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Dashboard placeholder page**

Replace `capex-app/src/app/page.tsx`:

```tsx
import { requireSession } from "@/lib/authz";
import { AppShell } from "@/components/app-shell";

export default async function DashboardPage() {
  const session = await requireSession();
  return (
    <AppShell session={session}>
      <h1 className="mb-4 text-2xl font-semibold">Dashboard</h1>
      <p className="text-muted-foreground">
        Welcome, {session.user.name}. Request queues will appear here in Phase 3.
      </p>
    </AppShell>
  );
}
```

(The root layout, fonts, favicon, and theme provider were already configured in Task 1.)

- [ ] **Step 4: Verify manually**

Run: `npm run dev`, sign in as admin.
Expected: sidebar is brand navy with the ARIA mark and shows all nav items (admin has ADMIN+REQUESTOR); header shows "System Administrator"; the theme toggle switches light/dark and every surface adapts (sidebar stays navy in both); Sign out works (redirects to /login).

- [ ] **Step 5: Commit**

```bash
cd ..
git add -A
git commit -m "feat: app shell with role-based nav, authz helpers"
```

---

### Task 7: Profile — change password

**Files:**
- Create: `capex-app/src/lib/user-service.ts`, `capex-app/src/app/profile/page.tsx`, `capex-app/src/app/profile/actions.ts`
- Test: `capex-app/tests/user-service.test.ts`

**Interfaces:**
- Consumes: `hashPassword`, `verifyPassword`, `prisma`.
- Produces: `changePassword(userId: string, current: string, next: string): Promise<{ ok: true } | { ok: false; error: string }>` from `@/lib/user-service` (more functions added in Task 8).

- [ ] **Step 1: Write failing test**

Create `capex-app/tests/user-service.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";
import { hashPassword, verifyPassword } from "@/lib/auth-service";
import { changePassword } from "@/lib/user-service";

describe("changePassword", () => {
  beforeEach(resetDb);

  async function makeUser() {
    return prisma.user.create({
      data: {
        username: "jdoe",
        email: "jdoe@uniteduptime.com",
        name: "Jane Doe",
        passwordHash: await hashPassword("OldPass1!"),
        roles: '["REQUESTOR"]',
      },
    });
  }

  it("changes the password when current password is correct", async () => {
    const u = await makeUser();
    const result = await changePassword(u.id, "OldPass1!", "NewPass1!");
    expect(result.ok).toBe(true);
    const updated = await prisma.user.findUniqueOrThrow({ where: { id: u.id } });
    expect(await verifyPassword("NewPass1!", updated.passwordHash)).toBe(true);
  });

  it("rejects when current password is wrong", async () => {
    const u = await makeUser();
    const result = await changePassword(u.id, "wrong", "NewPass1!");
    expect(result).toEqual({ ok: false, error: "Current password is incorrect." });
  });

  it("rejects passwords shorter than 8 characters", async () => {
    const u = await makeUser();
    const result = await changePassword(u.id, "OldPass1!", "short");
    expect(result.ok).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — cannot resolve `@/lib/user-service`.

- [ ] **Step 3: Implement**

Create `capex-app/src/lib/user-service.ts`:

```ts
import { prisma } from "@/lib/prisma";
import { hashPassword, verifyPassword } from "@/lib/auth-service";

export type ServiceResult = { ok: true } | { ok: false; error: string };

export async function changePassword(
  userId: string,
  current: string,
  next: string
): Promise<ServiceResult> {
  if (next.length < 8) {
    return { ok: false, error: "New password must be at least 8 characters." };
  }
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) return { ok: false, error: "User not found." };
  if (!(await verifyPassword(current, user.passwordHash))) {
    return { ok: false, error: "Current password is incorrect." };
  }
  await prisma.user.update({
    where: { id: userId },
    data: { passwordHash: await hashPassword(next) },
  });
  return { ok: true };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test` — expected: all pass.

- [ ] **Step 5: Profile page and action**

Create `capex-app/src/app/profile/actions.ts`:

```ts
"use server";

import { requireSession } from "@/lib/authz";
import { changePassword } from "@/lib/user-service";

export async function changePasswordAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string> {
  const session = await requireSession();
  const result = await changePassword(
    session.user.id,
    String(formData.get("current") ?? ""),
    String(formData.get("next") ?? "")
  );
  return result.ok ? "Password changed." : result.error;
}
```

Create `capex-app/src/app/profile/page.tsx`:

```tsx
import { requireSession } from "@/lib/authz";
import { AppShell } from "@/components/app-shell";
import { ChangePasswordForm } from "./change-password-form";

export default async function ProfilePage() {
  const session = await requireSession();
  return (
    <AppShell session={session}>
      <h1 className="mb-4 text-2xl font-semibold">My Profile</h1>
      <div className="max-w-md">
        <ChangePasswordForm />
      </div>
    </AppShell>
  );
}
```

Create `capex-app/src/app/profile/change-password-form.tsx`:

```tsx
"use client";

import { useActionState } from "react";
import { changePasswordAction } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ChangePasswordForm() {
  const [message, formAction, pending] = useActionState(changePasswordAction, undefined);
  return (
    <Card>
      <CardHeader><CardTitle>Change Password</CardTitle></CardHeader>
      <CardContent>
        <form action={formAction} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="current">Current password</Label>
            <Input id="current" name="current" type="password" required />
          </div>
          <div className="space-y-1">
            <Label htmlFor="next">New password (min 8 characters)</Label>
            <Input id="next" name="next" type="password" minLength={8} required />
          </div>
          {message && <p className="text-sm text-muted-foreground">{message}</p>}
          <Button type="submit" disabled={pending}>Change password</Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 6: Verify manually**

Run: `npm run dev` → sign in → /profile → change admin password to a new one, sign out, sign back in with the new password. (Then change it back or keep — note it.)

- [ ] **Step 7: Commit**

```bash
cd ..
git add -A
git commit -m "feat: profile page with change password (TDD)"
```

---

### Task 8: Admin — user management

**Files:**
- Modify: `capex-app/src/lib/user-service.ts`
- Create: `capex-app/src/app/admin/users/page.tsx`, `capex-app/src/app/admin/users/actions.ts`, `capex-app/src/app/admin/users/user-form.tsx`, `capex-app/src/app/admin/users/new/page.tsx`, `capex-app/src/app/admin/users/[id]/page.tsx`
- Test: `capex-app/tests/user-service.test.ts` (extend)

**Interfaces:**
- Produces (from `@/lib/user-service`):
  - `createUser(input: { username: string; email: string; name: string; password: string; roles: Role[]; divisionId: string | null }): Promise<ServiceResult>`
  - `updateUser(id: string, input: { name: string; email: string; roles: Role[]; divisionId: string | null; active: boolean }): Promise<ServiceResult>`
  - `adminResetPassword(id: string, newPassword: string): Promise<ServiceResult>`

- [ ] **Step 1: Write failing tests (append to `tests/user-service.test.ts`)**

```ts
import { createUser, updateUser, adminResetPassword } from "@/lib/user-service";

describe("admin user management", () => {
  beforeEach(resetDb);

  const input = {
    username: "bsmith",
    email: "bsmith@uniteduptime.com",
    name: "Bob Smith",
    password: "Temp1234!",
    roles: ["REQUESTOR", "APPROVER"] as const,
    divisionId: null,
  };

  it("creates a user with hashed password and roles", async () => {
    const result = await createUser({ ...input, roles: [...input.roles] });
    expect(result.ok).toBe(true);
    const u = await prisma.user.findUniqueOrThrow({ where: { username: "bsmith" } });
    expect(u.roles).toBe('["REQUESTOR","APPROVER"]');
    expect(await verifyPassword("Temp1234!", u.passwordHash)).toBe(true);
  });

  it("rejects duplicate username or email", async () => {
    await createUser({ ...input, roles: [...input.roles] });
    const dupUsername = await createUser({ ...input, roles: [...input.roles], email: "x@uniteduptime.com" });
    expect(dupUsername.ok).toBe(false);
    const dupEmail = await createUser({ ...input, roles: [...input.roles], username: "other" });
    expect(dupEmail.ok).toBe(false);
  });

  it("updates roles, division, and active flag", async () => {
    await createUser({ ...input, roles: [...input.roles] });
    const u = await prisma.user.findUniqueOrThrow({ where: { username: "bsmith" } });
    const division = await prisma.division.create({ data: { number: "200", name: "Dallas" } });
    const result = await updateUser(u.id, {
      name: "Robert Smith",
      email: u.email,
      roles: ["FINANCE"],
      divisionId: division.id,
      active: false,
    });
    expect(result.ok).toBe(true);
    const updated = await prisma.user.findUniqueOrThrow({ where: { id: u.id } });
    expect(updated.name).toBe("Robert Smith");
    expect(updated.roles).toBe('["FINANCE"]');
    expect(updated.divisionId).toBe(division.id);
    expect(updated.active).toBe(false);
  });

  it("admin reset password works and clears lockout", async () => {
    await createUser({ ...input, roles: [...input.roles] });
    const u = await prisma.user.findUniqueOrThrow({ where: { username: "bsmith" } });
    await prisma.user.update({
      where: { id: u.id },
      data: { failedLogins: 5, lockedUntil: new Date(Date.now() + 60_000) },
    });
    const result = await adminResetPassword(u.id, "NewTemp1!");
    expect(result.ok).toBe(true);
    const updated = await prisma.user.findUniqueOrThrow({ where: { id: u.id } });
    expect(await verifyPassword("NewTemp1!", updated.passwordHash)).toBe(true);
    expect(updated.failedLogins).toBe(0);
    expect(updated.lockedUntil).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `createUser` is not exported.

- [ ] **Step 3: Implement (append to `src/lib/user-service.ts`)**

```ts
import type { Role } from "@/lib/roles";
import { serializeRoles } from "@/lib/roles";

export async function createUser(input: {
  username: string;
  email: string;
  name: string;
  password: string;
  roles: Role[];
  divisionId: string | null;
}): Promise<ServiceResult> {
  if (input.password.length < 8) {
    return { ok: false, error: "Password must be at least 8 characters." };
  }
  const clash = await prisma.user.findFirst({
    where: { OR: [{ username: input.username }, { email: input.email }] },
  });
  if (clash) return { ok: false, error: "Username or email already exists." };
  await prisma.user.create({
    data: {
      username: input.username,
      email: input.email,
      name: input.name,
      passwordHash: await hashPassword(input.password),
      roles: serializeRoles(input.roles),
      divisionId: input.divisionId,
    },
  });
  return { ok: true };
}

export async function updateUser(
  id: string,
  input: { name: string; email: string; roles: Role[]; divisionId: string | null; active: boolean }
): Promise<ServiceResult> {
  const clash = await prisma.user.findFirst({
    where: { email: input.email, NOT: { id } },
  });
  if (clash) return { ok: false, error: "Email already in use." };
  await prisma.user.update({
    where: { id },
    data: {
      name: input.name,
      email: input.email,
      roles: serializeRoles(input.roles),
      divisionId: input.divisionId,
      active: input.active,
    },
  });
  return { ok: true };
}

export async function adminResetPassword(id: string, newPassword: string): Promise<ServiceResult> {
  if (newPassword.length < 8) {
    return { ok: false, error: "Password must be at least 8 characters." };
  }
  await prisma.user.update({
    where: { id },
    data: {
      passwordHash: await hashPassword(newPassword),
      failedLogins: 0,
      lockedUntil: null,
    },
  });
  return { ok: true };
}
```

(Consolidate imports at the top of the file: `import { serializeRoles, type Role } from "@/lib/roles";`)

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test` — expected: all pass.

- [ ] **Step 5: Server actions**

Create `capex-app/src/app/admin/users/actions.ts`:

```ts
"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireRole } from "@/lib/authz";
import { ROLES, type Role } from "@/lib/roles";
import { createUser, updateUser, adminResetPassword } from "@/lib/user-service";

function rolesFromForm(formData: FormData): Role[] {
  return ROLES.filter((r) => formData.get(`role_${r}`) === "on");
}

function divisionFromForm(formData: FormData): string | null {
  const v = String(formData.get("divisionId") ?? "");
  return v === "" || v === "none" ? null : v;
}

export async function createUserAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const result = await createUser({
    username: String(formData.get("username") ?? "").trim(),
    email: String(formData.get("email") ?? "").trim(),
    name: String(formData.get("name") ?? "").trim(),
    password: String(formData.get("password") ?? ""),
    roles: rolesFromForm(formData),
    divisionId: divisionFromForm(formData),
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/users");
  redirect("/admin/users");
}

export async function updateUserAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const result = await updateUser(String(formData.get("id")), {
    name: String(formData.get("name") ?? "").trim(),
    email: String(formData.get("email") ?? "").trim(),
    roles: rolesFromForm(formData),
    divisionId: divisionFromForm(formData),
    active: formData.get("active") === "on",
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/users");
  redirect("/admin/users");
}

export async function resetPasswordAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const result = await adminResetPassword(
    String(formData.get("id")),
    String(formData.get("password") ?? "")
  );
  return result.ok ? "Password reset." : result.error;
}
```

- [ ] **Step 6: User form component (shared by new/edit)**

Create `capex-app/src/app/admin/users/user-form.tsx`:

```tsx
"use client";

import { useActionState } from "react";
import { ROLES } from "@/lib/roles";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Division = { id: string; number: string; name: string };
type UserData = {
  id: string;
  username: string;
  email: string;
  name: string;
  roles: string[];
  divisionId: string | null;
  active: boolean;
};

export function UserForm({
  action,
  divisions,
  user,
}: {
  action: (prev: string | undefined, formData: FormData) => Promise<string | undefined>;
  divisions: Division[];
  user?: UserData;
}) {
  const [error, formAction, pending] = useActionState(action, undefined);

  return (
    <form action={formAction} className="max-w-lg space-y-4">
      {user && <input type="hidden" name="id" value={user.id} />}
      <div className="space-y-1">
        <Label htmlFor="username">Username</Label>
        <Input id="username" name="username" defaultValue={user?.username} required
          disabled={!!user} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="name">Full name</Label>
        <Input id="name" name="name" defaultValue={user?.name} required />
      </div>
      <div className="space-y-1">
        <Label htmlFor="email">Email</Label>
        <Input id="email" name="email" type="email" defaultValue={user?.email} required />
      </div>
      {!user && (
        <div className="space-y-1">
          <Label htmlFor="password">Temporary password (min 8 characters)</Label>
          <Input id="password" name="password" type="text" minLength={8} required />
        </div>
      )}
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Roles</legend>
        {ROLES.map((r) => (
          <label key={r} className="flex items-center gap-2 text-sm">
            <input type="checkbox" name={`role_${r}`}
              defaultChecked={user?.roles.includes(r) ?? r === "REQUESTOR"} />
            {r.charAt(0) + r.slice(1).toLowerCase()}
          </label>
        ))}
      </fieldset>
      <div className="space-y-1">
        <Label htmlFor="divisionId">Division</Label>
        <select id="divisionId" name="divisionId" defaultValue={user?.divisionId ?? "none"}
          className="w-full rounded-md border px-3 py-2 text-sm">
          <option value="none">— None —</option>
          {divisions.map((d) => (
            <option key={d.id} value={d.id}>{d.number} — {d.name}</option>
          ))}
        </select>
      </div>
      {user && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="active" defaultChecked={user.active} /> Active
        </label>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <Button type="submit" disabled={pending}>{user ? "Save changes" : "Create user"}</Button>
    </form>
  );
}
```

- [ ] **Step 7: List, new, and edit pages**

Create `capex-app/src/app/admin/users/page.tsx`:

```tsx
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { requireRole } from "@/lib/authz";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { parseRoles } from "@/lib/roles";

export default async function UsersPage() {
  const session = await requireRole("ADMIN");
  const users = await prisma.user.findMany({
    include: { division: true },
    orderBy: { name: "asc" },
  });

  return (
    <AppShell session={session}>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Users</h1>
        <Button asChild><Link href="/admin/users/new">Add User</Link></Button>
      </div>
      <div className="overflow-x-auto rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50 text-left">
            <tr>
              <th className="p-3">Name</th><th className="p-3">Username</th>
              <th className="p-3">Email</th><th className="p-3">Roles</th>
              <th className="p-3">Division</th><th className="p-3">Status</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b last:border-0">
                <td className="p-3">{u.name}</td>
                <td className="p-3">{u.username}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3 space-x-1">
                  {parseRoles(u.roles).map((r) => <Badge key={r} variant="secondary">{r}</Badge>)}
                </td>
                <td className="p-3">{u.division ? `${u.division.number} — ${u.division.name}` : "—"}</td>
                <td className="p-3">
                  <Badge variant={u.active ? "default" : "destructive"}>
                    {u.active ? "Active" : "Inactive"}
                  </Badge>
                </td>
                <td className="p-3">
                  <Link className="text-primary hover:underline" href={`/admin/users/${u.id}`}>Edit</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}
```

Create `capex-app/src/app/admin/users/new/page.tsx`:

```tsx
import { prisma } from "@/lib/prisma";
import { requireRole } from "@/lib/authz";
import { AppShell } from "@/components/app-shell";
import { UserForm } from "../user-form";
import { createUserAction } from "../actions";

export default async function NewUserPage() {
  const session = await requireRole("ADMIN");
  const divisions = await prisma.division.findMany({ where: { active: true }, orderBy: { number: "asc" } });
  return (
    <AppShell session={session}>
      <h1 className="mb-4 text-2xl font-semibold">Add User</h1>
      <UserForm action={createUserAction} divisions={divisions} />
    </AppShell>
  );
}
```

Create `capex-app/src/app/admin/users/[id]/page.tsx`:

```tsx
import { notFound } from "next/navigation";
import { prisma } from "@/lib/prisma";
import { requireRole } from "@/lib/authz";
import { AppShell } from "@/components/app-shell";
import { parseRoles } from "@/lib/roles";
import { UserForm } from "../user-form";
import { updateUserAction } from "../actions";
import { ResetPasswordForm } from "./reset-password-form";

export default async function EditUserPage({ params }: { params: Promise<{ id: string }> }) {
  const session = await requireRole("ADMIN");
  const { id } = await params;
  const user = await prisma.user.findUnique({ where: { id } });
  if (!user) notFound();
  const divisions = await prisma.division.findMany({ where: { active: true }, orderBy: { number: "asc" } });

  return (
    <AppShell session={session}>
      <h1 className="mb-4 text-2xl font-semibold">Edit User: {user.name}</h1>
      <div className="space-y-8">
        <UserForm
          action={updateUserAction}
          divisions={divisions}
          user={{
            id: user.id,
            username: user.username,
            email: user.email,
            name: user.name,
            roles: parseRoles(user.roles),
            divisionId: user.divisionId,
            active: user.active,
          }}
        />
        <ResetPasswordForm userId={user.id} />
      </div>
    </AppShell>
  );
}
```

Create `capex-app/src/app/admin/users/[id]/reset-password-form.tsx`:

```tsx
"use client";

import { useActionState } from "react";
import { resetPasswordAction } from "../actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ResetPasswordForm({ userId }: { userId: string }) {
  const [message, formAction, pending] = useActionState(resetPasswordAction, undefined);
  return (
    <Card className="max-w-lg">
      <CardHeader><CardTitle>Reset Password</CardTitle></CardHeader>
      <CardContent>
        <form action={formAction} className="space-y-4">
          <input type="hidden" name="id" value={userId} />
          <div className="space-y-1">
            <Label htmlFor="password">New temporary password (min 8 characters)</Label>
            <Input id="password" name="password" type="text" minLength={8} required />
          </div>
          {message && <p className="text-sm text-muted-foreground">{message}</p>}
          <Button type="submit" variant="outline" disabled={pending}>Reset password</Button>
        </form>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 8: Verify manually**

Run: `npm run dev` as admin:
- /admin/users lists the admin user.
- Add a user with REQUESTOR+APPROVER roles → appears in list.
- Edit them: change division, uncheck Active → list shows Inactive.
- Reset their password → "Password reset." message.
- Sign out; sign in as the new (inactive) user → rejected. Re-activate → sign-in works.
Run `npm test` — all pass.

- [ ] **Step 9: Commit**

```bash
cd ..
git add -A
git commit -m "feat: admin user management (create, edit, deactivate, reset password)"
```

---

### Task 9: Admin — divisions

**Files:**
- Create: `capex-app/src/lib/division-service.ts`, `capex-app/src/app/admin/divisions/page.tsx`, `capex-app/src/app/admin/divisions/actions.ts`, `capex-app/src/app/admin/divisions/division-form.tsx`
- Test: `capex-app/tests/division-service.test.ts`

**Interfaces:**
- Produces (from `@/lib/division-service`):
  - `createDivision(input: { number: string; name: string }): Promise<ServiceResult>`
  - `updateDivision(id: string, input: { name: string; l1ApproverId: string | null; active: boolean }): Promise<ServiceResult>`
- Note: a division's **L1 approver** is set here (per spec: L1 per-division, L2/L3 company-wide).

- [ ] **Step 1: Write failing tests**

Create `capex-app/tests/division-service.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";
import { createDivision, updateDivision } from "@/lib/division-service";

describe("division service", () => {
  beforeEach(resetDb);

  it("creates a division", async () => {
    const result = await createDivision({ number: "100", name: "Humble/Houston" });
    expect(result.ok).toBe(true);
    const d = await prisma.division.findUniqueOrThrow({ where: { number: "100" } });
    expect(d.name).toBe("Humble/Houston");
    expect(d.active).toBe(true);
  });

  it("rejects duplicate division numbers", async () => {
    await createDivision({ number: "100", name: "A" });
    const result = await createDivision({ number: "100", name: "B" });
    expect(result.ok).toBe(false);
  });

  it("requires the L1 approver to hold the APPROVER role", async () => {
    await createDivision({ number: "100", name: "A" });
    const d = await prisma.division.findUniqueOrThrow({ where: { number: "100" } });
    const nonApprover = await prisma.user.create({
      data: {
        username: "req", email: "req@uniteduptime.com", name: "Req Only",
        passwordHash: "x", roles: '["REQUESTOR"]',
      },
    });
    const bad = await updateDivision(d.id, { name: "A", l1ApproverId: nonApprover.id, active: true });
    expect(bad.ok).toBe(false);

    const approver = await prisma.user.create({
      data: {
        username: "app", email: "app@uniteduptime.com", name: "App Rover",
        passwordHash: "x", roles: '["APPROVER"]',
      },
    });
    const good = await updateDivision(d.id, { name: "A", l1ApproverId: approver.id, active: true });
    expect(good.ok).toBe(true);
    const updated = await prisma.division.findUniqueOrThrow({ where: { id: d.id } });
    expect(updated.l1ApproverId).toBe(approver.id);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — cannot resolve `@/lib/division-service`.

- [ ] **Step 3: Implement**

Create `capex-app/src/lib/division-service.ts`:

```ts
import { prisma } from "@/lib/prisma";
import { parseRoles } from "@/lib/roles";
import type { ServiceResult } from "@/lib/user-service";

export async function createDivision(input: {
  number: string;
  name: string;
}): Promise<ServiceResult> {
  const clash = await prisma.division.findUnique({ where: { number: input.number } });
  if (clash) return { ok: false, error: "Division number already exists." };
  await prisma.division.create({ data: { number: input.number, name: input.name } });
  return { ok: true };
}

export async function updateDivision(
  id: string,
  input: { name: string; l1ApproverId: string | null; active: boolean }
): Promise<ServiceResult> {
  if (input.l1ApproverId) {
    const approver = await prisma.user.findUnique({ where: { id: input.l1ApproverId } });
    if (!approver || !approver.active) return { ok: false, error: "Approver not found or inactive." };
    if (!parseRoles(approver.roles).includes("APPROVER")) {
      return { ok: false, error: "Selected user does not have the APPROVER role." };
    }
  }
  await prisma.division.update({
    where: { id },
    data: { name: input.name, l1ApproverId: input.l1ApproverId, active: input.active },
  });
  return { ok: true };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test` — expected: all pass.

- [ ] **Step 5: Actions and pages**

Create `capex-app/src/app/admin/divisions/actions.ts`:

```ts
"use server";

import { revalidatePath } from "next/cache";
import { requireRole } from "@/lib/authz";
import { createDivision, updateDivision } from "@/lib/division-service";

export async function createDivisionAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const result = await createDivision({
    number: String(formData.get("number") ?? "").trim(),
    name: String(formData.get("name") ?? "").trim(),
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/divisions");
  return "Division created.";
}

export async function updateDivisionAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const l1 = String(formData.get("l1ApproverId") ?? "none");
  const result = await updateDivision(String(formData.get("id")), {
    name: String(formData.get("name") ?? "").trim(),
    l1ApproverId: l1 === "none" ? null : l1,
    active: formData.get("active") === "on",
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/divisions");
  return "Division updated.";
}
```

Create `capex-app/src/app/admin/divisions/division-form.tsx`:

```tsx
"use client";

import { useActionState } from "react";
import { createDivisionAction, updateDivisionAction } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Approver = { id: string; name: string };
type DivisionData = {
  id: string; number: string; name: string;
  l1ApproverId: string | null; active: boolean;
};

export function NewDivisionForm() {
  const [message, formAction, pending] = useActionState(createDivisionAction, undefined);
  return (
    <form action={formAction} className="flex items-end gap-2">
      <div>
        <label className="text-sm font-medium">Number</label>
        <Input name="number" required className="w-28" />
      </div>
      <div className="flex-1">
        <label className="text-sm font-medium">Name</label>
        <Input name="name" required />
      </div>
      <Button type="submit" disabled={pending}>Add</Button>
      {message && <p className="pb-2 text-sm text-muted-foreground">{message}</p>}
    </form>
  );
}

export function EditDivisionRow({ division, approvers }: { division: DivisionData; approvers: Approver[] }) {
  const [message, formAction, pending] = useActionState(updateDivisionAction, undefined);
  return (
    <form action={formAction} className="flex items-center gap-2 border-b p-3 last:border-0">
      <input type="hidden" name="id" value={division.id} />
      <span className="w-20 text-sm font-mono">{division.number}</span>
      <Input name="name" defaultValue={division.name} className="w-56" />
      <select name="l1ApproverId" defaultValue={division.l1ApproverId ?? "none"}
        className="rounded-md border px-2 py-1.5 text-sm">
        <option value="none">— No L1 approver —</option>
        {approvers.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
      </select>
      <label className="flex items-center gap-1 text-sm">
        <input type="checkbox" name="active" defaultChecked={division.active} /> Active
      </label>
      <Button type="submit" size="sm" variant="outline" disabled={pending}>Save</Button>
      {message && <span className="text-xs text-muted-foreground">{message}</span>}
    </form>
  );
}
```

Create `capex-app/src/app/admin/divisions/page.tsx`:

```tsx
import { prisma } from "@/lib/prisma";
import { requireRole } from "@/lib/authz";
import { AppShell } from "@/components/app-shell";
import { parseRoles } from "@/lib/roles";
import { NewDivisionForm, EditDivisionRow } from "./division-form";

export default async function DivisionsPage() {
  const session = await requireRole("ADMIN");
  const divisions = await prisma.division.findMany({ orderBy: { number: "asc" } });
  const users = await prisma.user.findMany({ where: { active: true }, orderBy: { name: "asc" } });
  const approvers = users
    .filter((u) => parseRoles(u.roles).includes("APPROVER"))
    .map((u) => ({ id: u.id, name: u.name }));

  return (
    <AppShell session={session}>
      <h1 className="mb-4 text-2xl font-semibold">Divisions</h1>
      <div className="mb-6 max-w-2xl rounded-lg border bg-card p-4">
        <NewDivisionForm />
      </div>
      <div className="max-w-4xl rounded-lg border bg-card">
        <div className="flex gap-2 border-b bg-muted/50 p-3 text-sm font-medium">
          <span className="w-20">Number</span><span className="w-56">Name</span>
          <span>L1 Approver / Status</span>
        </div>
        {divisions.map((d) => (
          <EditDivisionRow key={d.id}
            division={{ id: d.id, number: d.number, name: d.name, l1ApproverId: d.l1ApproverId, active: d.active }}
            approvers={approvers} />
        ))}
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 6: Verify manually**

Run: `npm run dev` as admin → /admin/divisions:
- Division 100 Humble/Houston listed from seed.
- Add division 200 "Dallas" → appears.
- Assign an APPROVER-role user as L1 approver → saves; message shown.
Run `npm test` — all pass.

- [ ] **Step 7: Commit**

```bash
cd ..
git add -A
git commit -m "feat: admin division management with per-division L1 approver"
```

---

### Task 10: Admin — approval thresholds

**Files:**
- Create: `capex-app/src/lib/threshold-service.ts`, `capex-app/src/app/admin/thresholds/page.tsx`, `capex-app/src/app/admin/thresholds/actions.ts`, `capex-app/src/app/admin/thresholds/threshold-form.tsx`
- Test: `capex-app/tests/threshold-service.test.ts`

**Interfaces:**
- Produces (from `@/lib/threshold-service`):
  - `updateThresholds(input: { l1Max: number; l2Max: number; l2ApproverId: string | null; l3ApproverId: string | null }): Promise<ServiceResult>` — L3 max is always unlimited (null).
  - `getThresholds(): Promise<{ level: number; maxAmount: string | null; approverId: string | null; approverName: string | null }[]>`
- Business rule: `0 < l1Max < l2Max`. L2/L3 approvers must hold the APPROVER role.

- [ ] **Step 1: Write failing tests**

Create `capex-app/tests/threshold-service.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";
import { updateThresholds, getThresholds } from "@/lib/threshold-service";

async function seedLevels() {
  await prisma.approvalThreshold.createMany({
    data: [
      { level: 1, maxAmount: "10000" },
      { level: 2, maxAmount: "50000" },
      { level: 3, maxAmount: null },
    ],
  });
}

async function makeApprover(username: string) {
  return prisma.user.create({
    data: {
      username, email: `${username}@uniteduptime.com`, name: username,
      passwordHash: "x", roles: '["APPROVER"]',
    },
  });
}

describe("threshold service", () => {
  beforeEach(async () => {
    await resetDb();
    await seedLevels();
  });

  it("updates limits and approvers", async () => {
    const vp = await makeApprover("vp");
    const cfo = await makeApprover("cfo");
    const result = await updateThresholds({
      l1Max: 15000, l2Max: 75000, l2ApproverId: vp.id, l3ApproverId: cfo.id,
    });
    expect(result.ok).toBe(true);
    const rows = await getThresholds();
    expect(rows.find((r) => r.level === 1)?.maxAmount).toBe("15000");
    expect(rows.find((r) => r.level === 2)?.approverId).toBe(vp.id);
    expect(rows.find((r) => r.level === 3)?.maxAmount).toBeNull();
  });

  it("rejects when L1 max >= L2 max", async () => {
    const result = await updateThresholds({
      l1Max: 50000, l2Max: 50000, l2ApproverId: null, l3ApproverId: null,
    });
    expect(result.ok).toBe(false);
  });

  it("rejects non-approver users", async () => {
    const req = await prisma.user.create({
      data: {
        username: "r", email: "r@uniteduptime.com", name: "R",
        passwordHash: "x", roles: '["REQUESTOR"]',
      },
    });
    const result = await updateThresholds({
      l1Max: 10000, l2Max: 50000, l2ApproverId: req.id, l3ApproverId: null,
    });
    expect(result.ok).toBe(false);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — cannot resolve `@/lib/threshold-service`.

- [ ] **Step 3: Implement**

Create `capex-app/src/lib/threshold-service.ts`:

```ts
import { prisma } from "@/lib/prisma";
import { parseRoles } from "@/lib/roles";
import type { ServiceResult } from "@/lib/user-service";

async function validateApprover(userId: string | null): Promise<string | null> {
  if (!userId) return null;
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user || !user.active) return "Approver not found or inactive.";
  if (!parseRoles(user.roles).includes("APPROVER")) {
    return `${user.name} does not have the APPROVER role.`;
  }
  return null;
}

export async function updateThresholds(input: {
  l1Max: number;
  l2Max: number;
  l2ApproverId: string | null;
  l3ApproverId: string | null;
}): Promise<ServiceResult> {
  if (!(input.l1Max > 0)) return { ok: false, error: "Level 1 limit must be positive." };
  if (!(input.l1Max < input.l2Max)) {
    return { ok: false, error: "Level 1 limit must be less than Level 2 limit." };
  }
  for (const id of [input.l2ApproverId, input.l3ApproverId]) {
    const err = await validateApprover(id);
    if (err) return { ok: false, error: err };
  }
  await prisma.$transaction([
    prisma.approvalThreshold.update({
      where: { level: 1 },
      data: { maxAmount: String(input.l1Max), approverId: null },
    }),
    prisma.approvalThreshold.update({
      where: { level: 2 },
      data: { maxAmount: String(input.l2Max), approverId: input.l2ApproverId },
    }),
    prisma.approvalThreshold.update({
      where: { level: 3 },
      data: { maxAmount: null, approverId: input.l3ApproverId },
    }),
  ]);
  return { ok: true };
}

export async function getThresholds() {
  const rows = await prisma.approvalThreshold.findMany({
    include: { approver: true },
    orderBy: { level: "asc" },
  });
  return rows.map((r) => ({
    level: r.level,
    maxAmount: r.maxAmount === null ? null : r.maxAmount.toString(),
    approverId: r.approverId,
    approverName: r.approver?.name ?? null,
  }));
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test` — expected: all pass.

- [ ] **Step 5: Action and page**

Create `capex-app/src/app/admin/thresholds/actions.ts`:

```ts
"use server";

import { revalidatePath } from "next/cache";
import { requireRole } from "@/lib/authz";
import { updateThresholds } from "@/lib/threshold-service";

export async function updateThresholdsAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const l2 = String(formData.get("l2ApproverId") ?? "none");
  const l3 = String(formData.get("l3ApproverId") ?? "none");
  const result = await updateThresholds({
    l1Max: Number(formData.get("l1Max")),
    l2Max: Number(formData.get("l2Max")),
    l2ApproverId: l2 === "none" ? null : l2,
    l3ApproverId: l3 === "none" ? null : l3,
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/thresholds");
  return "Thresholds updated.";
}
```

Create `capex-app/src/app/admin/thresholds/threshold-form.tsx`:

```tsx
"use client";

import { useActionState } from "react";
import { updateThresholdsAction } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Approver = { id: string; name: string };
type Thresholds = {
  l1Max: string; l2Max: string;
  l2ApproverId: string | null; l3ApproverId: string | null;
};

export function ThresholdForm({ current, approvers }: { current: Thresholds; approvers: Approver[] }) {
  const [message, formAction, pending] = useActionState(updateThresholdsAction, undefined);

  const approverSelect = (name: string, value: string | null) => (
    <select name={name} defaultValue={value ?? "none"}
      className="w-full rounded-md border px-3 py-2 text-sm">
      <option value="none">— Not assigned —</option>
      {approvers.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
    </select>
  );

  return (
    <form action={formAction} className="max-w-xl space-y-6">
      <div className="rounded-lg border bg-card p-4">
        <h2 className="mb-2 font-medium">Level 1 — Division Manager</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Approver is set per division (Admin → Divisions). Requests up to this amount
          stop after Level 1 approval.
        </p>
        <Label htmlFor="l1Max">Approves up to ($)</Label>
        <Input id="l1Max" name="l1Max" type="number" min="1" step="0.01"
          defaultValue={current.l1Max} required />
      </div>
      <div className="rounded-lg border bg-card p-4">
        <h2 className="mb-2 font-medium">Level 2 — VP / Director (company-wide)</h2>
        <Label htmlFor="l2Max">Approves up to ($)</Label>
        <Input id="l2Max" name="l2Max" type="number" min="1" step="0.01"
          defaultValue={current.l2Max} required className="mb-3" />
        <Label>Approver</Label>
        {approverSelect("l2ApproverId", current.l2ApproverId)}
      </div>
      <div className="rounded-lg border bg-card p-4">
        <h2 className="mb-2 font-medium">Level 3 — CFO / CEO (company-wide)</h2>
        <p className="mb-3 text-sm text-muted-foreground">No upper limit — required for all requests above the Level 2 limit.</p>
        <Label>Approver</Label>
        {approverSelect("l3ApproverId", current.l3ApproverId)}
      </div>
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
      <Button type="submit" disabled={pending}>Save thresholds</Button>
    </form>
  );
}
```

Create `capex-app/src/app/admin/thresholds/page.tsx`:

```tsx
import { prisma } from "@/lib/prisma";
import { requireRole } from "@/lib/authz";
import { AppShell } from "@/components/app-shell";
import { parseRoles } from "@/lib/roles";
import { getThresholds } from "@/lib/threshold-service";
import { ThresholdForm } from "./threshold-form";

export default async function ThresholdsPage() {
  const session = await requireRole("ADMIN");
  const rows = await getThresholds();
  const users = await prisma.user.findMany({ where: { active: true }, orderBy: { name: "asc" } });
  const approvers = users
    .filter((u) => parseRoles(u.roles).includes("APPROVER"))
    .map((u) => ({ id: u.id, name: u.name }));

  const l1 = rows.find((r) => r.level === 1);
  const l2 = rows.find((r) => r.level === 2);
  const l3 = rows.find((r) => r.level === 3);

  return (
    <AppShell session={session}>
      <h1 className="mb-4 text-2xl font-semibold">Approval Thresholds</h1>
      <ThresholdForm
        current={{
          l1Max: l1?.maxAmount ?? "10000",
          l2Max: l2?.maxAmount ?? "50000",
          l2ApproverId: l2?.approverId ?? null,
          l3ApproverId: l3?.approverId ?? null,
        }}
        approvers={approvers}
      />
    </AppShell>
  );
}
```

- [ ] **Step 6: Verify manually**

Run: `npm run dev` as admin → /admin/thresholds:
- Shows seeded limits ($10,000 / $50,000 / unlimited).
- Set L2 approver to an APPROVER user, change L1 limit to 15000 → "Thresholds updated."
- Try L1 limit 100000 (> L2) → validation error shown.
Run `npm test` — all pass.

- [ ] **Step 7: Commit**

```bash
cd ..
git add -A
git commit -m "feat: admin approval thresholds configuration"
```

---

### Task 11: Phase 1 wrap-up — README and full verification

**Files:**
- Create: `capex-app/README.md`

**Interfaces:**
- Produces: documented dev setup for future contributors.

- [ ] **Step 1: Write README**

Create `capex-app/README.md`:

```markdown
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

## Structure

- `src/lib/` — business logic (unit-tested services)
- `src/app/` — routes: `/login`, `/profile`, `/admin/*` (Phase 1);
  `/requests/*` (Phase 2); dashboards & workflow (Phase 3)
```

- [ ] **Step 2: Full verification pass**

Run: `npm test` → all tests pass.
Run: `npm run build` → production build succeeds with no type errors.
Run: `npm run dev` and walk through: login (bad + good credentials), dashboard, profile password change, admin users CRUD, divisions, thresholds, sign out, middleware redirect when signed out.

- [ ] **Step 3: Commit**

```bash
cd ..
git add -A
git commit -m "docs: README and Phase 1 verification"
```

---

## Phase 1 exit criteria

- All Vitest suites green; `npm run build` clean.
- Admin can sign in, manage users/divisions/thresholds entirely from the UI.
- Non-admin users see only their permitted nav items and pages.
- Full schema exists for Phases 2–3 (requests, equipment, attachments, actions, notifications).

**Next plans:** Phase 2 (request wizard, drafts, attachments, detail page), Phase 3 (workflow engine, emails/reminders, dashboards, search/export/PDF, Azure deployment).
