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
