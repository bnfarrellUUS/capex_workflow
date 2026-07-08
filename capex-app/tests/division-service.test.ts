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
