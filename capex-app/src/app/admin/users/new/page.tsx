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
