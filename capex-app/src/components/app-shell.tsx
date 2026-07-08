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
