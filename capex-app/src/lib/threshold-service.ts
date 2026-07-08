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
