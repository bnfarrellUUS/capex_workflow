import { redirect } from "next/navigation";
import type { Session } from "next-auth";
import { auth } from "@/auth";
import type { Role } from "@/lib/roles";

export async function requireSession(): Promise<Session> {
  const session = await auth();
  if (!session?.user) redirect("/login");
  return session;
}

export async function requireRole(role: Role): Promise<Session> {
  const session = await requireSession();
  if (!session.user.roles.includes(role)) {
    throw new Error("Forbidden: missing role " + role);
  }
  return session;
}
