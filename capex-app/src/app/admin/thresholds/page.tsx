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
