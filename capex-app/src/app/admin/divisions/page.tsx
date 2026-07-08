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
