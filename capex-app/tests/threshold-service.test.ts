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
