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
        <Button render={<Link href="/admin/users/new">Add User</Link>} />
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
