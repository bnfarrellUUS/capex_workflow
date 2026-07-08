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
